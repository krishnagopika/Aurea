# Aurea API — Request & Response Examples

Base URL: `http://localhost:8000`
Interactive docs: `http://localhost:8000/docs`

---

## Health Check

```bash
curl http://localhost:8000/health
```

```json
{ "status": "ok", "service": "aurea-underwriting" }
```

---

## Auth

### Register

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "jane.smith@example.com", "password": "SecurePass123!"}'
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "jane.smith@example.com", "password": "SecurePass123!"}'
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

## Underwriting

> All underwriting endpoints require `Authorization: Bearer <token>`

### Assess a property — ACCEPT example

```bash
curl -X POST http://localhost:8000/api/v1/underwriting/assess \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"address": "42 Victoria Road, Manchester", "postcode": "M14 5TL"}'
```

```json
{
  "assessment_id": "7768b2c3d4e5f67890123456",
  "decision": "accept",
  "overall_risk_score": 18.0,
  "premium_multiplier": 0.9,
  "flood_risk_score": 5.0,
  "planning_risk_score": 12.0,
  "property_age_risk_score": 10.0,
  "risk_factors": [
    {
      "name": "Flood Risk",
      "score": 5.0,
      "weight": 0.45,
      "reasoning": "Flood Zone 1 — low probability; standard terms apply."
    },
    {
      "name": "Property Age Risk",
      "score": 10.0,
      "weight": 0.30,
      "reasoning": "Post-2012 construction in excellent condition, modern building standards."
    },
    {
      "name": "Planning & Development Risk",
      "score": 12.0,
      "weight": 0.25,
      "reasoning": "Low planning activity; 3 minor applications, no appeals."
    }
  ],
  "plain_english_narrative": "Your property at 42 Victoria Road has received a low overall risk score of 18/100. It sits comfortably in Flood Zone 1 with minimal flood risk, and its modern construction means structural risk is very low. We are pleased to offer standard coverage with a discounted premium multiplier of 0.9×.",
  "data_warnings": []
}
```

### Assess a property — REFER example

```bash
curl -X POST http://localhost:8000/api/v1/underwriting/assess \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"address": "10 Downing Street, London", "postcode": "SW1A 2AA"}'
```

```json
{
  "assessment_id": "6657a1b2c3d4e5f678901234",
  "decision": "refer",
  "overall_risk_score": 62.5,
  "premium_multiplier": 1.75,
  "flood_risk_score": 45.0,
  "planning_risk_score": 30.0,
  "property_age_risk_score": 65.0,
  "risk_factors": [
    {
      "name": "Flood Risk",
      "score": 45.0,
      "weight": 0.45,
      "reasoning": "Flood Zone 2 — medium probability of flooding, elevated premium applies."
    },
    {
      "name": "Property Age Risk",
      "score": 65.0,
      "weight": 0.30,
      "reasoning": "Pre-1930 construction requires structural survey before acceptance."
    },
    {
      "name": "Planning & Development Risk",
      "score": 30.0,
      "weight": 0.25,
      "reasoning": "Moderate planning activity with 8 nearby applications; no major developments."
    }
  ],
  "plain_english_narrative": "Your property at 10 Downing Street has been assessed with an overall risk score of 63/100. The main concern is its location in Flood Risk Zone 2. We are referring this application to a senior underwriter for manual review. A premium multiplier of 1.75× applies, pending final confirmation.",
  "data_warnings": []
}
```

### Assess a property — DECLINE example

```bash
curl -X POST http://localhost:8000/api/v1/underwriting/assess \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"address": "1 Flooding Lane, York", "postcode": "YO1 9HH"}'
```

```json
{
  "assessment_id": "8879c3d4e5f6789012345678",
  "decision": "decline",
  "overall_risk_score": 84.0,
  "premium_multiplier": 3.0,
  "flood_risk_score": 85.0,
  "planning_risk_score": 66.0,
  "property_age_risk_score": 80.0,
  "risk_factors": [
    {
      "name": "Flood Risk",
      "score": 85.0,
      "weight": 0.45,
      "reasoning": "Flood Zone 3 — high probability of flooding; policy exclusion applies."
    },
    {
      "name": "Property Age Risk",
      "score": 80.0,
      "weight": 0.30,
      "reasoning": "Pre-1900 construction; mandatory structural survey required."
    },
    {
      "name": "Planning & Development Risk",
      "score": 66.0,
      "weight": 0.25,
      "reasoning": "High planning activity with 2 active appeals and 1 large development nearby."
    }
  ],
  "plain_english_narrative": "Unfortunately we are unable to offer standard coverage for this property. The property is located in Flood Zone 3, which exceeds our standard policy terms. We recommend contacting the Flood Re scheme for specialist coverage.",
  "data_warnings": ["IBEX planning data returned limited results for this postcode"]
}
```

### Get assessment history

```bash
curl http://localhost:8000/api/v1/underwriting/history \
  -H "Authorization: Bearer <token>"
```

```json
[
  {
    "assessment_id": "6657a1b2c3d4e5f678901234",
    "decision": "refer",
    "overall_risk_score": 62.5,
    "premium_multiplier": 1.75,
    ...
  },
  {
    "assessment_id": "7768b2c3d4e5f67890123456",
    "decision": "accept",
    "overall_risk_score": 18.0,
    "premium_multiplier": 0.9,
    ...
  }
]
```

---

## Decision thresholds

| Score | Decision | Meaning |
|-------|----------|---------|
| < 60  | `accept`  | Standard coverage offered |
| 60–79 | `refer`   | Manual senior underwriter review required |
| ≥ 80  | `decline` | Outside standard policy terms |

## Premium multiplier range

| Risk level | Multiplier |
|------------|------------|
| Very low   | 0.8× – 1.0× |
| Low–medium | 1.0× – 1.5× |
| Medium–high | 1.5× – 2.5× |
| Very high  | 2.5× – 3.0× |

---

## Error responses

### 401 Unauthorized
```json
{ "detail": "Invalid or expired token" }
```

### 400 Bad Request (duplicate email)
```json
{ "detail": "Email already registered" }
```

### 500 Internal Server Error
```json
{ "detail": "Description of what went wrong" }
```
