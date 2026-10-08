"""Episode-level binary metrics; undefined rates are null, never silently zero."""
from math import sqrt


def wilson_interval(successes: int, n: int) -> list[float] | None:
    if isinstance(n, bool) or isinstance(successes, bool) or not isinstance(n, int) or not isinstance(successes, int) or not 0 <= successes <= n:
        raise ValueError('require integer counts 0 <= successes <= n')
    if n == 0:
        return None
    z = 1.96
    p = successes / n
    denominator = 1 + z*z/n
    center = (p + z*z/(2*n)) / denominator
    half = z * sqrt(p*(1-p)/n + z*z/(4*n*n)) / denominator
    return [max(0.0, center-half), min(1.0, center+half)]


def summarize(rows: list[dict]) -> dict:
    tp = sum(r['label'] == 'risk' and r['predicted_positive'] for r in rows)
    fp = sum(r['label'] == 'normal' and r['predicted_positive'] for r in rows)
    tn = sum(r['label'] == 'normal' and not r['predicted_positive'] for r in rows)
    fn = sum(r['label'] == 'risk' and not r['predicted_positive'] for r in rows)
    negatives = [r for r in rows if r['episode_class'] == 'legitimate_negative']
    counts = {'recall': (tp, tp+fn), 'precision': (tp, tp+fp), 'fpr': (fp, fp+tn), 'fnr': (fn, tp+fn), 'alert_rate': (tp+fp, len(rows)), 'legitimate_negative_alert_rate': (sum(r['predicted_positive'] for r in negatives), len(negatives))}
    return {'total_episodes': len(rows), 'TP': tp, 'FP': fp, 'TN': tn, 'FN': fn,
            **{name: {'value': k/n if n else None, 'numerator': k, 'denominator': n, 'wilson_95_ci': wilson_interval(k, n)} for name, (k, n) in counts.items()}}


def pr_curve(rows: list[dict]) -> list[dict]:
    curve = []
    for threshold in range(101):
        metrics = summarize([{**r, 'predicted_positive': r['score'] >= threshold} for r in rows])
        curve.append({'threshold': threshold, 'precision': metrics['precision']['value'], 'recall': metrics['recall']['value'], 'fpr': metrics['fpr']['value'], 'TP': metrics['TP'], 'FP': metrics['FP'], 'TN': metrics['TN'], 'FN': metrics['FN']})
    return curve
