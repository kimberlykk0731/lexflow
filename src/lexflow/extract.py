"""Fact extraction: LLM first, deterministic keyword rules as fallback."""
from __future__ import annotations

import json
import re
from datetime import date

from .elements import ElementSchema, Field
from .llm import BaseLLM, extract_json

CORRECTION_MARKERS = ["更正", "不是", "其实", "说错", "改一下", "纠正", "记错了", "应该是", "准确地说"]

REASON_PATTERNS = [
    (["严重违纪", "违反规章制度", "违反公司制度", "旷工", "打架", "偷", "泄密", "严重违规"], "严重违纪"),
    (["不胜任", "能力不行", "绩效不达标", "考核不合格", "干不了"], "不胜任工作"),
    (["裁员", "经济性裁员", "优化", "缩减"], "经济性裁员"),
    (["客观情况", "部门撤销", "搬迁", "业务调整", "岗位取消"], "客观情况重大变化"),
    (["试用期"], "试用期不符合录用条件"),
]

WHO_PATTERNS = [
    (["协商一致", "协商解除", "双方同意"], "协商一致解除"),
    (["我辞职", "自己辞职", "主动离职", "我提的离职"], "劳动者辞职"),
    (["辞退", "开除", "解除", "让我走", "不用来了", "单方"], "单位单方解除"),
]

CLAIM_PATTERNS = [
    (["继续履行", "回去上班", "恢复劳动关系", "继续干"], "要求继续履行"),
    (["赔偿金", "2n", "二倍", "赔钱", "赔偿"], "要求赔偿金"),
]


def _norm_enum(text: str, field: Field, patterns: list[tuple[list[str], str]]) -> str | None:
    low = text.lower()
    for keys, value in patterns:
        if value in field.options and any(k.lower() in low for k in keys):
            return value
    for opt in field.options:
        core = re.sub(r"[（(].*?[）)]", "", opt)
        if core and core in text:
            return opt
    return None


CN_NUM = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
          "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNIT = {"十": 10, "百": 100, "千": 1000}


def _cn_num(text: str) -> int:
    total, section, num = 0, 0, 0
    for ch in text:
        if ch in CN_NUM:
            num = CN_NUM[ch]
        elif ch in CN_UNIT:
            section += (num or 1) * CN_UNIT[ch]
            num = 0
        elif ch in "零〇":
            num = 0
        else:
            raise ValueError(text)
    return section + num


DATE_RE = re.compile(r"(\d{4})\s*[年\-/.\s]\s*(\d{1,2})\s*(?:[月\-/.\s]\s*(\d{1,2})\s*日?)?")

DATE_CUES = {
    "dismiss_date": ["辞退", "解除", "开除", "通知我", "通知解除", "解除通知", "让我走", "离职", "走人", "不用来"],
    "start_date": ["入职", "上班", "进公司", "签合同", "开始干"],
    "accident_date": ["事故", "车祸", "撞", "发生"],
}

_DATE_PAT = r"(\d{4})\s*[年\-/.\s]\s*(\d{1,2})\s*(?:[月\-/.\s]\s*(\d{1,2})\s*日?)?"


def _iso(y, m, d) -> str | None:
    try:
        return date(int(y), int(m), int(d) if d else 1).isoformat()
    except ValueError:
        return None


def find_correction_date(text: str) -> str | None:
    """Extract the *corrected* date from phrases like

    "不是2025年8月，是2026年2月1日" / "是2026年2月1日，不是2025年8月".
    """
    p1 = re.search(rf"不(?:是|对)\s*{_DATE_PAT}.*?(?:而是|是|改为|应为)\s*{_DATE_PAT}", text)
    if p1:
        return _iso(p1.group(4), p1.group(5), p1.group(6))
    p2 = re.search(rf"(?:而是|是|改为|应为)\s*{_DATE_PAT}.*?不(?:是|对)\s*{_DATE_PAT}", text)
    if p2:
        return _iso(p2.group(1), p2.group(2), p2.group(3))
    return None


def _cue_distance(text: str, pos: int, cues: list[str]) -> int:
    best = 999
    for cue in cues:
        start = text.find(cue)
        while start != -1:
            edge = start + len(cue) if start < pos else start
            best = min(best, abs(edge - pos))
            start = text.find(cue, start + 1)
    return best


def _correction_target(text: str, facts: dict, date_fields: list[tuple[str, object]]) -> str | None:
    order = ["accident_date", "start_date", "dismiss_date"]
    cues = {"accident_date": ["事故", "车祸", "撞"],
            "start_date": ["入职", "上班", "签合同"],
            "dismiss_date": ["解除", "辞退", "通知", "开除"]}
    keys = [k for k, _ in date_fields]
    for key in order:
        if key in keys and any(c in text for c in cues[key]):
            return key
    present = [k for k in keys if k in facts]
    if len(present) == 1:
        return present[0]
    return keys[0] if keys else None


def find_dates(text: str, today: date) -> list[tuple[int, str, str]]:
    """Return [(position, iso_date, precision)] with precision in {day, month}."""
    out: list[tuple[int, str, str]] = []
    for m in DATE_RE.finditer(text):
        year, month = int(m.group(1)), int(m.group(2))
        day = int(m.group(3)) if m.group(3) else 1
        try:
            out.append((m.start(), date(year, month, day).isoformat(),
                        "day" if m.group(3) else "month"))
        except ValueError:
            continue
    if not out:
        m = re.search(r"(去年|今年|前年)\s*(\d{1,2})\s*月", text)
        if m:
            year = today.year + {"去年": -1, "今年": 0, "前年": -2}[m.group(1)]
            try:
                out.append((m.start(), date(year, int(m.group(2)), 1).isoformat(), "month"))
            except ValueError:
                pass
    return out


def find_money(text: str) -> float | None:
    # “一万五”“一万五千”“两万三千”
    m = re.search(r"([一二两三四五六七八九十]+)\s*万\s*([一二两三四五六七八九十千零百]*)", text)
    if m:
        base = _cn_num(m.group(1)) * 10000
        suffix = m.group(2)
        if suffix:
            if len(suffix) == 1 and suffix in CN_NUM:
                base += CN_NUM[suffix] * 1000
            else:
                try:
                    base += _cn_num(suffix)
                except ValueError:
                    pass
        return float(base)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(万|w|千|k)\s*(\d)?", text, re.I)
    if m:
        value = float(m.group(1)) * (10000 if m.group(2).lower() in ("万", "w") else 1000)
        if m.group(3):
            value += float(m.group(3)) * (1000 if m.group(2).lower() in ("万", "w") else 100)
        return value
    # bare number: require a money cue and reject years
    m = re.search(r"(\d{2,7})(?!\s*年)", text)
    if m and re.search(r"工资|月薪|薪水|收入|元|块|赔", text):
        return float(m.group(1))
    return None


class Extractor:
    def __init__(self, schema: ElementSchema, llm: BaseLLM):
        self.schema = schema
        self.llm = llm
        self.last_source = "rules"
        self.usage = {"prompt": 0, "completion": 0, "calls": 0}

    def extract(self, text: str, facts: dict, case_type: str | None = None) -> dict:
        """Return {case_type, facts, corrections, unknown, correction_hint, source}."""
        if self.llm.enabled:
            result = self._llm_extract(text, facts, case_type)
            if result:
                self.last_source = "llm"
                return result
        self.last_source = "rules"
        return self._rule_extract(text, facts, case_type)

    # ------------------------------------------------------------------ LLM
    def _llm_extract(self, text: str, facts: dict, case_type: str | None) -> dict | None:
        fields = []
        for ctype in ([case_type] if case_type else self.schema.types()):
            for f in self.schema.fields(ctype):
                fields.append({
                    "key": f.key, "label": f.label, "type": f.type,
                    "options": f.options,
                    "critical": self.schema.is_critical(f, facts, ctype),
                })
        system = (
            "你是法律咨询系统的信息抽取模块。只做事实抽取，不做法律判断。"
            "从用户最新一句话中抽取结构化事实，输出严格 JSON，不要输出任何解释。\n"
            "规则：\n"
            "1. 只抽取用户明确说出的内容，不要推测；听不出来的字段不要填。\n"
            "2. 日期统一为 YYYY-MM-DD；只知道年月时填 YYYY-MM-01。\n"
            "3. 金额统一为数字（元），如“月薪一万二”输出 12000。\n"
            "4. 枚举字段只能取 options 中的一个值；拿不准就不要填。\n"
            "5. 用户明确更正此前说法时，把新值同时放进 corrections。\n"
            "6. unknown 填用户明确表示“不知道/记不清”的字段 key。\n"
            "输出格式：{\"case_type\":\"...\",\"facts\":{...},\"corrections\":{...},\"unknown\":[...]}"
        )
        user = json.dumps({
            "case_type": case_type,
            "known_facts": {k: v for k, v in facts.items() if v not in (None, "")},
            "fields": fields,
            "user_text": text,
        }, ensure_ascii=False)
        res = self.llm.complete([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ], temperature=0)
        if res.ok:
            self.usage["prompt"] += res.prompt_tokens
            self.usage["completion"] += res.completion_tokens
            self.usage["calls"] += 1
        if not res.ok:
            return None
        data = extract_json(res.text)
        if not isinstance(data, dict) or ("facts" not in data and "corrections" not in data):
            return None
        ctype = data.get("case_type") or case_type
        if ctype not in self.schema.types():
            ctype = case_type or self.schema.classify(text)[0][0]
        hint = any(m in text for m in CORRECTION_MARKERS)
        # The model normalises "2024年1月" to 2024-01-01; recover month
        # precision from the original text so the gate can ask for the day.
        precision = {}
        seen = {iso: prec for _, iso, prec in find_dates(text, date.today())}
        for key, value in (data.get("facts") or {}).items():
            if isinstance(value, str) and value in seen:
                precision[key] = seen[value]
        return self._clean(ctype, data.get("facts", {}), data.get("corrections", {}),
                           data.get("unknown", []), hint, source="llm",
                           precision=precision)

    # ---------------------------------------------------------------- rules
    def _rule_extract(self, text: str, facts: dict, case_type: str | None) -> dict:
        ctype = case_type
        if not ctype:
            ranked = self.schema.classify(text)
            ctype = ranked[0][0] if ranked and ranked[0][1] > 0 else "labor_dismissal"
        found: dict = {}
        precision: dict[str, str] = {}
        today = date.today()
        hint = any(m in text for m in CORRECTION_MARKERS)

        def field(key):
            return self.schema.field(ctype, key)

        date_fields = [(k, field(k)) for k in ("dismiss_date", "start_date", "accident_date")]
        date_fields = [(k, f) for k, f in date_fields if f]
        dates = find_dates(text, today)
        if hint and dates:
            corrected = find_correction_date(text)
            if corrected:
                target = _correction_target(text, facts, date_fields)
                if target:
                    found[target] = corrected
                    precision[target] = "day"
        for pos, iso, prec in dates:
            if iso in found.values():
                continue
            scores = {key: _cue_distance(text, pos, DATE_CUES.get(key, []))
                      for key, _ in date_fields}
            if scores:
                best_key = min(scores, key=lambda k: scores[k])
                if scores[best_key] <= 12:
                    if best_key not in found:
                        found[best_key] = iso
                        precision[best_key] = prec
                    continue
            if hint:
                present = [k for k, _ in date_fields if k in facts]
                if len(present) == 1:
                    found[present[0]] = iso
                    precision[present[0]] = prec
                    continue
            for key, _ in date_fields:
                if key not in found and key not in facts:
                    found[key] = iso
                    precision[key] = prec
                    break
        if field("monthly_wage") and re.search(r"工资|月薪|薪水|收入|万|千|元|块", text):
            money = find_money(text)
            if money:
                found["monthly_wage"] = money
        if field("who_initiated"):
            v = _norm_enum(text, field("who_initiated"), WHO_PATTERNS)
            if v:
                found["who_initiated"] = v
        if field("stated_reason") and re.search(r"理由|因为|说|以|违纪|不胜任|裁员|试用期|客观", text):
            v = _norm_enum(text, field("stated_reason"), REASON_PATTERNS)
            if v:
                found["stated_reason"] = v
        if field("claim_type"):
            v = _norm_enum(text, field("claim_type"), CLAIM_PATTERNS)
            if v:
                found["claim_type"] = v
        if field("rule_publicized") and re.search(r"公示|告知|签收|手册|制度|规章|培训|学习|看过|发给我", text):
            if re.search(r"没(有)?(给我)?(看|发|公示|告知|签收|培训|组织)|未(公示|告知|签收|培训)|"
                         r"没见过|没发过|没看过|没签收|没有签收", text):
                found["rule_publicized"] = "没有公示告知"
            elif re.search(r"签收|公示过|发过|培训过|学习过|有公示|签过字|看过|组织过", text):
                found["rule_publicized"] = "有签收或公示"
            elif re.search(r"记不清|不知道", text):
                found["rule_publicized"] = "记不清"
        if field("rule_exists") and re.search(r"制度|手册|规章", text):
            if re.search(r"没有(成文)?(制度|手册)|无制度|没有规章|没(有)?(员工)?手册", text):
                found["rule_exists"] = "没有成文制度"
            elif re.search(r"有(成文)?(制度|手册)|有规章|员工手册|公司手册", text):
                found["rule_exists"] = "有成文制度"
        if field("misconduct_proof") and re.search(r"证据|监控|录像|签字|检讨|证人|口头", text):
            if re.search(r"只有口头|口头说|领导说|没人看见|没有书面|没有证据|没证据", text):
                found["misconduct_proof"] = "只有口头指认"
            elif re.search(r"证人", text):
                found["misconduct_proof"] = "有证人但无书面材料"
            elif re.search(r"监控|录像|邮件|签字|书面|检讨", text):
                found["misconduct_proof"] = "有书面证据"
        if field("union_notified") and re.search(r"工会", text):
            if re.search(r"没有工会|没建工会", text):
                found["union_notified"] = "公司没有工会"
            elif re.search(r"没(有)?通知|未通知", text):
                found["union_notified"] = "没有通知"
            elif re.search(r"通知了|已通知", text):
                found["union_notified"] = "已通知工会"
        if field("arbitration_filed") and re.search(r"仲裁", text):
            found["arbitration_filed"] = "已申请" if re.search(r"申请了|已申请|已经仲裁", text) else "没有申请"
        if field("training_or_transfer") and re.search(r"培训|调岗|换岗", text):
            found["training_or_transfer"] = "没有" if re.search(r"没有|没给|未", text) else "有培训或调岗"
        if field("notice_30d") and re.search(r"三十天|30天|代通知金|提前通知", text):
            if re.search(r"代通知金", text):
                found["notice_30d"] = "支付了代通知金"
            elif re.search(r"没有|都没", text):
                found["notice_30d"] = "都没有"
            else:
                found["notice_30d"] = "提前三十日通知"
        if field("rule_democratic") and re.search(r"民主程序|职工代表大会|职工代表|协商", text):
            found["rule_democratic"] = "没有经过" if re.search(r"没有|没经|未", text) else "经过了民主程序"
        if field("responsibility"):
            if re.search(r"对方全责|他全责|全责", text):
                found["responsibility"] = "对方全责"
            elif re.search(r"主要责任|主责", text):
                found["responsibility"] = "对方主要责任"
            elif re.search(r"同等责任|各一半", text):
                found["responsibility"] = "同等责任"
            elif re.search(r"次要责任|次责", text):
                found["responsibility"] = "对方次要责任"
            elif re.search(r"还没认定|未认定|没有认定书", text):
                found["responsibility"] = "尚未认定"
        if field("injury"):
            if re.search(r"死亡|去世|身亡", text):
                found["injury"] = "死亡"
            elif re.search(r"[一二三四五六七八九十]级伤残|伤残等级", text):
                found["injury"] = "已鉴定伤残等级"
            elif re.search(r"伤残|残疾", text):
                found["injury"] = "伤残但未鉴定"
            elif re.search(r"重伤", text):
                found["injury"] = "重伤"
            elif re.search(r"轻伤|擦伤|一般伤", text):
                found["injury"] = "一般伤害"
        if field("residence"):
            if re.search(r"农村|农业户口", text):
                found["residence"] = "农村"
            elif re.search(r"城镇|城市户口|非农业", text):
                found["residence"] = "城镇"
        if field("insurance") and re.search(r"保险|交强险|三者险|商业险", text):
            if re.search(r"没有保险|没保险|未投保", text):
                found["insurance"] = "没有保险"
            elif re.search(r"交强险和商业|商业三者险", text):
                found["insurance"] = "交强险和商业险"
            elif re.search(r"交强险", text):
                found["insurance"] = "仅有交强险"
        if field("employment") and re.search(r"上班|工作|送货|公司车|办公事|职务", text):
            found["employment"] = "执行工作任务" if not re.search(r"私事|下班", text) else "个人事务"

        unknown = [k for k, v in found.items() if v in ("记不清", "不知道")]
        hint = any(m in text for m in CORRECTION_MARKERS)
        return self._clean(ctype, found, {}, unknown, hint, source="rules",
                           precision=precision)

    # ---------------------------------------------------------------- clean
    def _clean(self, ctype: str, facts: dict, corrections: dict,
               unknown: list, correction_hint: bool, source: str,
               precision: dict | None = None) -> dict:
        clean_facts: dict = {}
        clean_corr: dict = {}
        for target, raw_map in ((clean_facts, facts), (clean_corr, corrections)):
            for key, raw in (raw_map or {}).items():
                f = self.schema.field(ctype, key)
                if not f or raw in (None, ""):
                    continue
                value = self.schema.normalize(f, raw)
                if value in (None, ""):
                    continue
                target[key] = value
        return {"case_type": ctype, "facts": clean_facts, "corrections": clean_corr,
                "unknown": [u for u in unknown if isinstance(u, str)],
                "precision": precision or {},
                "correction_hint": correction_hint, "source": source}
