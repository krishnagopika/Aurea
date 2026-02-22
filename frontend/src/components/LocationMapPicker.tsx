'use client'

/**
 * LocationMapPicker
 * -----------------
 * Interactive Leaflet map that lets the user:
 *  1. Search for an address via a search box (Nominatim)
 *  2. Click anywhere on the map to place a pin
 *  3. Drag the pin to refine the location
 *
 * On any pin placement / drag, reverse-geocodes the point and
 * calls onLocationSelect with { address, postcode, lat, lon }.
 *
 * Uses dynamic import inside the component to avoid SSR issues
 * (Leaflet reads `window` on load).
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { Search, Loader2, X } from 'lucide-react'

export interface PickedLocation {
  address: string
  postcode: string
  lat: number
  lon: number
}

interface Props {
  /** Called whenever the pin moves or an address is selected */
  onLocationSelect: (loc: PickedLocation) => void
  /** Initial marker position (optional) */
  initialLat?: number
  initialLon?: number
}

// ── Nominatim helpers ──────────────────────────────────────────────────────

async function nominatimSearch(query: string): Promise<Array<{
  display_name: string
  lat: string
  lon: string
  address: { postcode?: string; house_number?: string; road?: string; city?: string; town?: string; village?: string }
}>> {
  const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query + ', UK')}&countrycodes=gb&format=json&limit=5&addressdetails=1`
  const res = await fetch(url, { headers: { 'Accept-Language': 'en' } })
  if (!res.ok) return []
  return res.json()
}

async function nominatimReverse(lat: number, lon: number): Promise<{
  display_name: string
  address: { postcode?: string; house_number?: string; road?: string; city?: string; town?: string }
} | null> {
  const url = `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json&addressdetails=1`
  const res = await fetch(url, { headers: { 'Accept-Language': 'en' } })
  if (!res.ok) return null
  return res.json()
}

function formatAddress(addr: { house_number?: string; road?: string; city?: string; town?: string; village?: string }, fallback: string): string {
  const { house_number, road, city, town, village } = addr
  const locality = city ?? town ?? village ?? ''
  const parts = [house_number, road, locality].filter(Boolean)
  return parts.length > 0 ? parts.join(', ') : fallback
}

// ── Component ──────────────────────────────────────────────────────────────

export default function LocationMapPicker({ onLocationSelect, initialLat = 51.505, initialLon = -0.09 }: Props) {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const markerRef = useRef<any>(null)

  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<Awaited<ReturnType<typeof nominatimSearch>>>([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [searching, setSearching] = useState(false)
  const [reversing, setReversing] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // ── Reverse geocode and fire callback ──────────────────────────────────
  const reverseAndNotify = useCallback(async (lat: number, lon: number) => {
    setReversing(true)
    try {
      const result = await nominatimReverse(lat, lon)
      if (result) {
        onLocationSelect({
          lat,
          lon,
          address: formatAddress(result.address, result.display_name),
          postcode: result.address.postcode ?? '',
        })
      }
    } finally {
      setReversing(false)
    }
  }, [onLocationSelect])

  // ── Initialise Leaflet (client-side only) ──────────────────────────────
  useEffect(() => {
    if (typeof window === 'undefined' || mapRef.current) return

    // Leaflet must be loaded dynamically to avoid SSR crashes
    import('leaflet').then((L) => {
      // Fix default marker icon (webpack strips the default URLs)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (L.Icon.Default.prototype as any)._getIconUrl
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
        iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
      })

      if (!mapContainerRef.current) return

      // Guard against React StrictMode double-invoke: if the container already
      // has a Leaflet instance attached, skip re-initialisation.
      if (mapContainerRef.current.dataset.leafletInitialised === 'true') return
      mapContainerRef.current.dataset.leafletInitialised = 'true'

      // UK bounding box — used only to restrict pin placement, not panning
      const UK_BOUNDS = L.latLngBounds(
        L.latLng(49.5, -8.2),   // SW corner (SW of Cornwall)
        L.latLng(61.0, 2.2),    // NE corner (Shetland)
      )

      const map = L.map(mapContainerRef.current).setView([initialLat, initialLon], 13)

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map)

      const marker = L.marker([initialLat, initialLon], { draggable: true }).addTo(map)

      marker.on('dragend', () => {
        const pos = marker.getLatLng()
        if (!UK_BOUNDS.contains(pos)) {
          // Snap marker back to last valid UK position
          marker.setLatLng(markerRef.current?._latlng ?? UK_BOUNDS.getCenter())
          return
        }
        reverseAndNotify(pos.lat, pos.lng)
      })

      map.on('click', (e: { latlng: { lat: number; lng: number } }) => {
        // Only place pin if click is within UK
        if (!UK_BOUNDS.contains(e.latlng)) return
        marker.setLatLng([e.latlng.lat, e.latlng.lng])
        reverseAndNotify(e.latlng.lat, e.latlng.lng)
      })

      mapRef.current = map
      markerRef.current = marker
    })

    return () => {
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
        markerRef.current = null
      }
      if (mapContainerRef.current) {
        mapContainerRef.current.dataset.leafletInitialised = 'false'
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Move marker programmatically ───────────────────────────────────────
  const flyTo = useCallback((lat: number, lon: number) => {
    if (!mapRef.current || !markerRef.current) return
    markerRef.current.setLatLng([lat, lon])
    mapRef.current.flyTo([lat, lon], 16, { duration: 1 })
  }, [])

  // ── Search box handlers ────────────────────────────────────────────────
  const handleSearchChange = (val: string) => {
    setSearchQuery(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (!val.trim() || val.length < 4) {
      setSearchResults([])
      setShowDropdown(false)
      return
    }
    debounceRef.current = setTimeout(async () => {
      setSearching(true)
      try {
        const results = await nominatimSearch(val)
        setSearchResults(results)
        setShowDropdown(results.length > 0)
      } finally {
        setSearching(false)
      }
    }, 500)
  }

  const handleResultClick = (res: (typeof searchResults)[number]) => {
    const lat = parseFloat(res.lat)
    const lon = parseFloat(res.lon)
    flyTo(lat, lon)
    setSearchQuery(formatAddress(res.address, res.display_name))
    setShowDropdown(false)
    onLocationSelect({
      lat,
      lon,
      address: formatAddress(res.address, res.display_name),
      postcode: res.address.postcode ?? '',
    })
  }

  // Close dropdown on outside click
  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [])

  return (
    <div className="space-y-2">
      {/* Search bar */}
      <div className="relative" ref={dropdownRef}>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search address on map..."
            className="w-full rounded-lg border border-slate-300 bg-white pl-9 pr-10 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
          />
          {searching && (
            <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-slate-400" />
          )}
          {!searching && searchQuery && (
            <button
              type="button"
              onClick={() => { setSearchQuery(''); setSearchResults([]); setShowDropdown(false) }}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        {showDropdown && searchResults.length > 0 && (
          <ul className="absolute left-0 right-0 top-full mt-1 z-[9999] bg-white border border-slate-200 rounded-lg shadow-xl max-h-52 overflow-y-auto">
            {searchResults.map((res, i) => (
              <li
                key={i}
                onMouseDown={(e) => { e.preventDefault(); handleResultClick(res) }}
                className="px-4 py-2.5 cursor-pointer hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-b-0"
              >
                <p className="text-sm font-medium text-slate-800 truncate">
                  {formatAddress(res.address, res.display_name)}
                </p>
                <p className="text-[11px] text-slate-400 truncate mt-0.5">{res.display_name}</p>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Map container */}
      <div className="relative rounded-xl overflow-hidden border border-slate-200">
        <div ref={mapContainerRef} style={{ height: 300, width: '100%' }} />
        {reversing && (
          <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex items-center gap-2 bg-white/90 backdrop-blur-sm text-xs text-slate-600 px-3 py-1.5 rounded-full shadow border border-slate-200 z-[1000]">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />
            Getting address...
          </div>
        )}
        <p className="absolute bottom-2 right-2 text-[10px] text-slate-400 bg-white/80 px-1.5 py-0.5 rounded z-[1000]">
          Click map or drag pin
        </p>
      </div>
    </div>
  )
}
