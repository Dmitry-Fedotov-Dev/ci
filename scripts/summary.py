#!/usr/bin/env python3
"""Markdown for the CI run summary page ($GITHUB_STEP_SUMMARY) and the job log.

  summary.py [--lang en|ru] functional [--all-steps] <reports dir> <scenario>...
      from k6 JUnit reports: steps of failed scenarios only; --all-steps adds passed ones, folded
  summary.py [--lang en|ru] load <summary.json> <title> [<note>]
      from k6 --summary-export: key SIP/RTP metrics and every threshold
  summary.py [--lang en|ru] gosec <gosec.json> [<note>]
      gosec findings grouped by rule
"""
import collections
import json
import os
import sys
import xml.etree.ElementTree as ET

T = {
    "en": {
        "no_report": "no report: k6 stopped before writing it",
        "of_passed": "{p} of {n} passed",
        "step": "Step",
        "func_bad": "### ❌ Functional: {b} of {n} scenarios failed",
        "func_ok": "### ✅ Functional: {n} scenarios passed",
        "func_head": "| Scenario | Result | Steps | Failed step |",
        "ms": "ms",
        "calls": "Calls", "per_sec": "{r:.2f} CAPS",
        "success": "Successful calls (200 OK)",
        "setup": "Setup time p95", "pdd": "Post-dial delay p95", "first": "First response to INVITE p95",
        "heard": "Legs that heard audio",
        "score": "Audio score p50 / min / p95",
        "jitter": "Jitter p95", "rtp": "RTP packets received / lost",
        "retrans": "SIP retransmissions", "dropped": "Dropped iterations",
        "checks": "Checks", "of": "{a:,} of {b:,}",
        "load_bad": "### ❌ Load (xk6-sip): {b} of {n} thresholds crossed",
        "load_ok": "### ✅ Load (xk6-sip): {n} thresholds held",
        "load_head": "| Metric | Value | Threshold | |",
        "gosec_head": "### gosec: {n} findings",
        "gosec_cols": "| Rule | Count | What |",
    },
    "ru": {
        "no_report": "нет отчёта: k6 остановился, не записав его",
        "of_passed": "{p} из {n}",
        "step": "Шаг",
        "func_bad": "### ❌ Звонки (xk6-sip): провалено {b} из {n} сценариев",
        "func_ok": "### ✅ Звонки (xk6-sip): {n} сценариев прошли",
        "func_head": "| Сценарий | Итог | Шаги | Проваленный шаг |",
        "ms": "мс",
        "calls": "Звонков", "per_sec": "{r:.2f} в секунду",
        "success": "Успешные звонки (200 OK)",
        "setup": "От INVITE до 200 OK, p95", "pdd": "Задержка после набора, p95", "first": "Первый ответ на INVITE, p95",
        "heard": "В трубке был звук",
        "score": "Качество звука p50 / min / p95",
        "jitter": "Джиттер p95", "rtp": "RTP получено / потеряно",
        "retrans": "Повторы SIP", "dropped": "Пропущенные итерации",
        "checks": "Проверки", "of": "{a:,} из {b:,}",
        "load_bad": "### ❌ Нагрузка (xk6-sip): пробито {b} из {n} порогов",
        "load_ok": "### ✅ Нагрузка (xk6-sip): {n} порогов соблюдены",
        "load_head": "| Метрика | Значение | Порог | |",
        "gosec_head": "### gosec: {n} замечаний",
        "gosec_cols": "| Правило | Сколько | Что |",
    },
}
L = T["en"]


def cell(s):
    return str(s).replace("|", "\\|")


def functional(reports, scenarios, all_steps):
    rows, details = [], []
    for s in scenarios:
        path = os.path.join(reports, f"{s}.xml")
        if not os.path.exists(path):
            rows.append(f"| {s} | ❌ | — | {L['no_report']} |")
            continue
        cases = [(c.get("name"), c.find("failure") is None) for c in ET.parse(path).iter("testcase")]
        steps = [c for c in cases if not c[0].startswith("threshold ")]
        failed = [name for name, ok in cases if not ok]
        passed = sum(ok for _, ok in steps)
        ok = not failed
        # a failed step stops the scenario, so it is the first failure
        first = next((n for n, good in steps if not good), failed[0] if failed else "")
        count = f"{len(steps)}" if ok else L["of_passed"].format(p=passed, n=len(steps))
        rows.append(f"| {s} | {'✅' if ok else '❌'} | {count} | {cell(first)} |")
        table = "\n".join(f"| {'✅' if good else '❌'} | {cell(n)} |" for n, good in cases)
        steps_md = f"| | {L['step']} |\n|---|---|\n{table}\n"
        if all_steps:  # summary page: every scenario, passed ones folded
            details.append(f"<details{'' if ok else ' open'}><summary>{'✅' if ok else '❌'} {s}</summary>\n\n"
                           f"{steps_md}\n</details>\n")
        elif not ok:  # job log: steps only for a failed scenario
            details.append(f"#### ❌ {s}\n\n{steps_md}")
    bad = sum("| ❌ |" in r for r in rows)
    head = L["func_bad"].format(b=bad, n=len(rows)) if bad else L["func_ok"].format(n=len(rows))
    print(f"{head}\n\n{L['func_head']}\n|---|---|---|---|")
    print("\n".join(rows) + "\n")
    print("\n".join(details))
    return bad == 0


def ms(v):
    return f"{v:.2f} {L['ms']}" if v < 10 else f"{v:.0f} {L['ms']}"


def pct(v):
    return f"{v * 100:.2f}".rstrip("0").rstrip(".") + "%"


def load(path, title, note=""):
    m = json.load(open(path, encoding="utf-8"))["metrics"]
    get = lambda name, key, default=None: m.get(name, {}).get(key, default)
    shown, rows = set(), []

    def row(label, value, metric=None):
        th = m.get(metric, {}).get("thresholds", {}) if metric else {}
        shown.add(metric)
        mark = ("❌" if any(th.values()) else "✅") if th else ""  # summary-export: true = crossed
        rows.append(f"| {label} | {value} | {cell(', '.join(th)) or '—'} | {mark} |")

    calls = get("sip_call_success", "passes", 0) + get("sip_call_success", "fails", 0)
    row(L["calls"], f"{calls}, " + L["per_sec"].format(r=get("sip_call_results", "rate", 0) or 0))
    if "sip_call_success" in m:
        row(L["success"], pct(get("sip_call_success", "value")), "sip_call_success")
    for metric, key in [("sip_call_setup_time", "setup"), ("sip_post_dial_delay", "pdd"),
                        ("sip_invite_first_response_time", "first")]:
        if metric in m:
            row(L[key], ms(get(metric, "p(95)")), metric)
    if "rtp_audio_heard" in m:
        row(L["heard"], pct(get("rtp_audio_heard", "value")), "rtp_audio_heard")
    if "rtp_audio_score" in m:
        vals = [get("rtp_audio_score", k) for k in ("med", "min", "p(95)")]
        row(L["score"], " / ".join(f"{v:.3f}" for v in vals if v is not None), "rtp_audio_score")
    if "rtp_jitter" in m:
        row(L["jitter"], ms(get("rtp_jitter", "p(95)")), "rtp_jitter")
    if "rtp_packets_received" in m:
        row(L["rtp"], f"{get('rtp_packets_received', 'count', 0):,} / {get('rtp_packets_lost', 'count', 0):,}")
    if "sip_retransmissions" in m:
        row(L["retrans"], get("sip_retransmissions", "count"), "sip_retransmissions")
    if "dropped_iterations" in m:
        row(L["dropped"], get("dropped_iterations", "count"), "dropped_iterations")
    if "checks" in m:
        p, f = get("checks", "passes", 0), get("checks", "fails", 0)
        row(L["checks"], L["of"].format(a=p, b=p + f), "checks")
    for metric, v in m.items():  # thresholds on anything not listed above (project metrics)
        if v.get("thresholds") and metric not in shown:
            val = v.get("value", v.get("p(95)", v.get("count", "")))
            row(metric, pct(val) if isinstance(val, float) and 0 <= val <= 1 and "value" in v else val, metric)

    ths = [crossed for v in m.values() for crossed in v.get("thresholds", {}).values()]
    bad = sum(ths)
    head = L["load_bad"].format(b=bad, n=len(ths)) if bad else L["load_ok"].format(n=len(ths))
    print(f"{head}\n\n{title}\n\n{L['load_head']}\n|---|---|---|---|")
    print("\n".join(rows))
    if note:
        print(f"\n{note}\n")
    return bad == 0


def gosec(path, note=""):
    issues = json.load(open(path, encoding="utf-8")).get("Issues") or []
    by_rule = collections.Counter(i["rule_id"] for i in issues)
    what = {i["rule_id"]: i["details"].split(" conversion ")[0] for i in issues}
    print(L["gosec_head"].format(n=len(issues)) + "\n")
    if issues:
        print(f"{L['gosec_cols']}\n|---|---|---|")
        for rule, n in by_rule.most_common():
            print(f"| {rule} | {n} | {cell(what[rule])} |")
    if note:
        print(f"\n{note}\n")
    return True


def main(argv):
    global L
    if len(argv) >= 2 and argv[0] == "--lang":
        L = T.get(argv[1], T["en"])
        argv = argv[2:]
    if len(argv) >= 2 and argv[0] == "functional":
        args = [a for a in argv[1:] if a != "--all-steps"]
        functional(args[0], args[1:], "--all-steps" in argv)
    elif len(argv) in (3, 4) and argv[0] == "load":
        load(argv[1], argv[2], argv[3] if len(argv) == 4 else "")
    elif len(argv) in (2, 3) and argv[0] == "gosec":
        gosec(argv[1], argv[2] if len(argv) == 3 else "")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
