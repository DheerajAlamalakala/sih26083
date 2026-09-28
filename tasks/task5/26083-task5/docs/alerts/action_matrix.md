# Heat Action Matrix

## Rule Version

1.1

## Important Note

The alert thresholds in this document are PROJECT-DEFINED PROTOTYPE RULES.

They are not official government heat-health alert thresholds.

They are used for the prototype action engine and can be replaced later if an authoritative threshold source is adopted.

## Alert Levels

| Alert Level | Risk Range | Notification Required |
|---|---:|---|
| LOW | 0–30 | No |
| MODERATE | 31–60 | Yes |
| HIGH | 61–80 | Yes |
| CRITICAL | 81–100 | Yes |

## LOW

### Advisory

Heat conditions are currently at a lower risk level. Continue monitoring local conditions and follow routine heat-safety guidance.

### Municipal Actions

- Monitor local heat conditions
- Maintain readiness of cooling facilities

### Notification

Notification is not required.

---

## MODERATE

### Advisory

Heat conditions require increased attention. Residents should follow heat-safety guidance and remain aware of changing local conditions.

### Municipal Actions

- Prepare cooling centres
- Increase healthcare preparedness
- Monitor power demand

### Notification

Notification is required.

---

## HIGH

### Advisory

High heat-health risk is expected. Follow heat-safety guidance and reduce exposure to prolonged heat where possible.

### Municipal Actions

- Prepare or open cooling centres
- Increase healthcare preparedness
- Prepare for increased power demand
- Consider shifting outdoor work hours

### Notification

Notification is required.

---

## CRITICAL

### Advisory

Very high heat-health risk is expected. Follow heat-safety guidance and minimize prolonged exposure to extreme heat.

### Municipal Actions

- Open or activate cooling centres
- Strengthen healthcare preparedness
- Prepare for elevated power demand
- Shift outdoor work hours where appropriate

### Notification

Notification is required.

---

## Prototype Action-Risk Rule

The current prototype uses:

```text
health_risk = max(mortality_risk_0_100, hospitalization_risk_0_100)

action_risk_0_100 =
    (health_risk × 0.70)
    + (vulnerability_0_100 × 0.30)
    + persistence_adjustment