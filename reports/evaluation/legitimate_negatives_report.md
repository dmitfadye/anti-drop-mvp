# Legitimate negatives — synthetic fixtures only

Not validated banking accuracy. These cases test false-positive sensitivity.

{
  "total_episodes": 11,
  "TP": 0,
  "FP": 1,
  "TN": 10,
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
    "value": 0.09090909090909091,
    "numerator": 1,
    "denominator": 11,
    "wilson_95_ci": [
      0.01623175226282597,
      0.3773646254862038
    ]
  },
  "fnr": {
    "value": null,
    "numerator": 0,
    "denominator": 0,
    "wilson_95_ci": null
  },
  "alert_rate": {
    "value": 0.09090909090909091,
    "numerator": 1,
    "denominator": 11,
    "wilson_95_ci": [
      0.01623175226282597,
      0.3773646254862038
    ]
  },
  "legitimate_negative_alert_rate": {
    "value": 0.09090909090909091,
    "numerator": 1,
    "denominator": 11,
    "wilson_95_ci": [
      0.01623175226282597,
      0.3773646254862038
    ]
  }
}

Alerted episode IDs:
- ep_6c9eac9ef7f00f00
