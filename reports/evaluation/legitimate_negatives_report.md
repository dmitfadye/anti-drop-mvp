# Legitimate negatives — synthetic fixtures only

Not validated banking accuracy. These cases test false-positive sensitivity.

{
  "total_episodes": 9,
  "TP": 0,
  "FP": 1,
  "TN": 8,
  "FN": 0,
  "recall": {
    "value": null,
    "numerator": 0,
    "denominator": 0,
    "wilson_95_ci": null
  },
  "precision": {
    "value": 0.0,
    "numerator": 0,
    "denominator": 1,
    "wilson_95_ci": [
      0.0,
      0.7934567085261071
    ]
  },
  "fpr": {
    "value": 0.1111111111111111,
    "numerator": 1,
    "denominator": 9,
    "wilson_95_ci": [
      0.019890371327130535,
      0.4350062147680601
    ]
  },
  "fnr": {
    "value": null,
    "numerator": 0,
    "denominator": 0,
    "wilson_95_ci": null
  },
  "alert_rate": {
    "value": 0.1111111111111111,
    "numerator": 1,
    "denominator": 9,
    "wilson_95_ci": [
      0.019890371327130535,
      0.4350062147680601
    ]
  },
  "legitimate_negative_alert_rate": {
    "value": 0.1111111111111111,
    "numerator": 1,
    "denominator": 9,
    "wilson_95_ci": [
      0.019890371327130535,
      0.4350062147680601
    ]
  }
}

Alerted episode IDs:
- ep_6c9eac9ef7f00f00
