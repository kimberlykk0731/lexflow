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


CN_INT = r"[一二三四五六七八九十两\d]+"


def _int(text: str) -> int | None:
    text = (text or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    try:
        return _cn_num(text)
    except ValueError:
        return None


DATE_RE = re.compile(r"(\d{4})\s*[年\-/.\s]\s*(\d{1,2})\s*(?:[月\-/.\s]\s*(\d{1,2})\s*日?)?")

DATE_CUES = {
    "dismiss_date": ["辞退", "解除", "开除", "通知我", "通知解除", "解除通知", "让我走", "离职", "走人", "不用来"],
    "start_date": ["入职", "上班", "进公司", "签合同", "开始干"],
    "accident_date": ["事故", "车祸", "撞", "发生"],
    "injury_date": ["工伤", "受伤", "伤", "事故"],
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
    order = ["accident_date", "injury_date", "start_date", "dismiss_date"]
    cues = {"accident_date": ["事故", "车祸", "撞"],
            "injury_date": ["工伤", "受伤", "伤"],
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
        m = re.search(r"(去年|今年|前年)\s*(\d{1,2})\s*月\s*(?:(\d{1,2})\s*[日号]?)?", text)
        if m:
            year = today.year + {"去年": -1, "今年": 0, "前年": -2}[m.group(1)]
            try:
                out.append((m.start(), date(year, int(m.group(2)), int(m.group(3)) if m.group(3) else 1).isoformat(),
                            "day" if m.group(3) else "month"))
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
    def __init__(self, schema: ElementSchema, llm: BaseLLM, today: date | None = None):
        self.schema = schema
        self.llm = llm
        self.today = today or date.today()
        self.last_source = "rules"
        self.usage = {"prompt": 0, "completion": 0, "calls": 0}

    def extract(self, text: str, facts: dict,
                case_type: str | list[str] | None = None) -> dict:
        """Return {case_type, facts, corrections, unknown, correction_hint, source}.

        ``case_type`` may be a single claim id or a list of active claims.
        """
        claims = [case_type] if isinstance(case_type, str) else list(case_type or [])
        if self.llm.enabled:
            result = self._llm_extract(text, facts, claims)
            if result:
                allowed = {f.key for f in self.schema.fields(claims)} if claims else set()
                if claims:
                    for part in ("facts", "corrections", "precision"):
                        result[part] = {k: v for k, v in result.get(part, {}).items() if k in allowed}
                    result["unknown"] = [k for k in result["unknown"] if k in allowed]
                result["facts"].update(result["corrections"])
                self.last_source = "llm"
                return result
        self.last_source = "rules"
        return self._rule_extract(text, facts, claims)

    # ------------------------------------------------------------------ LLM
    def _llm_extract(self, text: str, facts: dict,
                     claims: list[str]) -> dict | None:
        fields = []
        seen = set()
        for ctype in (claims or self.schema.types()):
            for f in self.schema.fields(ctype):
                if f.key in seen:
                    continue
                seen.add(f.key)
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
            "7. text 类型的值保留用户原话中的连续片段，只去掉字段标签；期间和年度不要改写或转成ISO日期。\n"
            "8. known_facts只作上下文，最新一句没有提及的不要重新输出。只说赔偿时不要擅自区分经济补偿和赔偿金。\n"
            "输出格式：{\"case_type\":\"...\",\"facts\":{...},\"corrections\":{...},\"unknown\":[...]}"
        )
        user = json.dumps({
            "claims": claims,
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
        ctype = data.get("case_type")
        if ctype not in (claims or self.schema.types()):
            ctype = claims[0] if claims else ""
        if not ctype:
            ranked = self.schema.classify(text)
            ctype = ranked[0][0] if ranked and ranked[0][1] > 0 else ""
        hint = any(m in text for m in CORRECTION_MARKERS)
        # The model normalises "2024年1月" to 2024-01-01; recover month
        # precision from the original text so the gate can ask for the day.
        precision = {}
        seen = {iso: prec for _, iso, prec in find_dates(text, self.today)}
        for key, value in (data.get("facts") or {}).items():
            if isinstance(value, str) and value in seen:
                precision[key] = seen[value]
        # Preserve explicitly labelled text independently of model formatting.
        # This only uses the current utterance, never the hidden evaluation sheet.
        for f in fields:
            if f["type"] != "text":
                continue
            pattern = re.escape(f["label"]) + r"(?:是|为|[，,:：])\s*([^。；;\n]+)"
            match = re.search(pattern, text)
            if match and not re.search(r"不清楚|不知道|记不清|无法确认", match.group(1)):
                target = "corrections" if f["key"] in (data.get("corrections") or {}) else "facts"
                data.setdefault(target, {})[f["key"]] = match.group(1).strip()
        return self._clean(ctype, data.get("facts", {}), data.get("corrections", {}),
                           data.get("unknown", []), hint, source="llm",
                           precision=precision)

    # ---------------------------------------------------------------- rules
    def _rule_extract(self, text: str, facts: dict,
                      claims: list[str]) -> dict:
        ctype = claims[0] if claims else ""
        if not ctype:
            ranked = self.schema.classify(text)
            ctype = ranked[0][0] if ranked and ranked[0][1] > 0 else ""
        found: dict = {}
        precision: dict[str, str] = {}
        today = self.today
        hint = any(m in text for m in CORRECTION_MARKERS)

        def available(key):
            # only facts declared by an *active* claim are extracted; otherwise
            # every pattern would fire on every sentence
            return any(self.schema.declares(c, key) for c in claims)

        def put(key, value):
            if key not in found and available(key) and value not in (None, ""):
                found[key] = value

        # ---- dates -----------------------------------------------------
        date_fields = []
        for c in claims:
            for f in self.schema.fields(c):
                if f.type == "date" and f.key not in [k for k, _ in date_fields]:
                    date_fields.append((f.key, f))
        if not date_fields:
            date_fields = [(k, self.schema.field_any(k)) for k in
                           ("dismiss_date", "start_date", "injury_date", "accident_date")]
            date_fields = [(k, f) for k, f in date_fields if f]
        dates = find_dates(text, today)
        if hint and dates:
            corrected = find_correction_date(text)
            if corrected:
                target = _correction_target(text, facts, date_fields)
                if target:
                    put(target, corrected)
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
                        put(best_key, iso)
                        precision[best_key] = prec
                    continue
            if hint:
                present = [k for k, _ in date_fields if k in facts]
                if len(present) == 1:
                    put(present[0], iso)
                    precision[present[0]] = prec
                    continue
            for key, _ in date_fields:
                if key not in found and key not in facts:
                    put(key, iso)
                    precision[key] = prec
                    break

        # ---- money -----------------------------------------------------
        money = find_money(text)
        if money:
            if re.search(r"欠|拖|没发|未发|少发|克扣", text) and available("wage_owed"):
                put("wage_owed", money)
            elif re.search(r"医疗费|医药费|住院费|治疗费", text):
                put("medical_cost" if available("medical_cost") else "treatment_cost", money)
            elif re.search(r"工资|月薪|薪水|收入", text) and available("monthly_wage"):
                put("monthly_wage", money)
            elif available("amount_in_dispute"):
                put("amount_in_dispute", money)

        # ---- dismissal -------------------------------------------------
        if available("who_initiated"):
            v = _norm_enum(text, self.schema.field_any("who_initiated"), WHO_PATTERNS)
            if v:
                put("who_initiated", v)
        if available("stated_reason") and re.search(r"理由|因为|说|以|违纪|不胜任|裁员|试用期|客观|不续签", text):
            v = _norm_enum(text, self.schema.field_any("stated_reason"), REASON_PATTERNS)
            if v:
                put("stated_reason", v)
        if available("claim_type"):
            v = _norm_enum(text, self.schema.field_any("claim_type"), CLAIM_PATTERNS)
            if v:
                put("claim_type", v)
        if available("rule_publicized") and re.search(r"公示|告知|签收|手册|制度|规章|培训|学习|看过|发给我", text):
            if re.search(r"没(有)?(给我)?(看|发|公示|告知|签收|培训|组织)|未(公示|告知|签收|培训)|"
                         r"没见过|没发过|没看过|没签收|没有签收", text):
                put("rule_publicized", "没有公示告知")
            elif re.search(r"签收|公示过|发过|培训过|学习过|有公示|签过字|看过|组织过", text):
                put("rule_publicized", "有签收或公示")
            elif re.search(r"记不清|不知道", text):
                put("rule_publicized", "记不清")
        if available("rule_exists") and re.search(r"制度|手册|规章", text):
            if re.search(r"没有(成文)?(制度|手册)|无制度|没有规章|没(有)?(员工)?手册", text):
                put("rule_exists", "没有成文制度")
            elif re.search(r"有(成文)?(制度|手册)|有规章|员工手册|公司手册", text):
                put("rule_exists", "有成文制度")
        if available("misconduct_proof") and re.search(r"证据|监控|录像|签字|检讨|证人|口头", text):
            if re.search(r"只有口头|口头说|领导说|没人看见|没有书面|没有证据|没证据", text):
                put("misconduct_proof", "只有口头指认")
            elif re.search(r"证人", text):
                put("misconduct_proof", "有证人但无书面材料")
            elif re.search(r"监控|录像|邮件|签字|书面|检讨", text):
                put("misconduct_proof", "有书面证据")
        if available("union_notified") and re.search(r"工会", text):
            if re.search(r"没有工会|没建工会", text):
                put("union_notified", "公司没有工会")
            elif re.search(r"没(有)?通知|未通知", text):
                put("union_notified", "没有通知")
            elif re.search(r"通知了|已通知", text):
                put("union_notified", "已通知工会")
        if available("training_or_transfer") and re.search(r"培训|调岗|换岗", text):
            put("training_or_transfer", "没有" if re.search(r"没有|没给|未", text) else "有培训或调岗")
        if available("notice_30d") and re.search(r"三十天|30天|代通知金|提前通知", text):
            if re.search(r"代通知金", text):
                put("notice_30d", "支付了代通知金")
            elif re.search(r"没有|都没", text):
                put("notice_30d", "都没有")
            else:
                put("notice_30d", "提前三十日通知")
        if available("rule_democratic") and re.search(r"民主程序|职工代表大会|职工代表|协商", text):
            put("rule_democratic", "没有经过" if re.search(r"没有|没经|未", text) else "经过了民主程序")
        if available("forced_resignation_reason"):
            if re.search(r"没(有)?(缴|交|买).{0,4}社保|不缴社保", text):
                put("forced_resignation_reason", "未依法缴纳社保")
            elif re.search(r"欠薪|拖欠工资|没发工资", text):
                put("forced_resignation_reason", "未及时足额支付工资")
        if available("compensation_paid"):
            if re.search(r"没(有)?(给|支付).{0,4}(补偿|赔偿)|一分没给", text):
                put("compensation_paid", "未支付任何补偿")
            elif re.search(r"给了?\s*2[nN]|二倍|2N", text):
                put("compensation_paid", "支付了2N")
            elif re.search(r"给了?\s*n\+1|N\+1", text):
                put("compensation_paid", "支付了N+1")
            elif re.search(r"给了?\s*n(?!\+)|N的补偿", text):
                put("compensation_paid", "支付了N")
        if available("contract_expired") and re.search(r"到期|不续签|合同期满", text):
            put("contract_expired", "合同到期不续签")
        if available("pregnancy_status"):
            if re.search(r"怀孕|孕期", text):
                put("pregnancy_status", "孕期")
            elif re.search(r"产假|产期", text):
                put("pregnancy_status", "产期")
            elif re.search(r"哺乳", text):
                put("pregnancy_status", "哺乳期")

        if available("employer"):
            m = re.search(r"(?:公司|单位)(?:叫|是|名为|全称是|名称是)\s*([^\s，。；、]{2,40})", text)
            if m:
                put("employer", m.group(1))

        # ---- wage ------------------------------------------------------
        if available("wage_type"):
            for keys, value in [(["基本工资", "底薪"], "基本工资"),
                                (["提成", "奖金", "绩效"], "提成/奖金"),
                                (["年终奖"], "年终奖"),
                                (["加班费"], "加班费")]:
                if any(k in text for k in keys):
                    put("wage_type", value)
                    break
        if available("wage_reason"):
            for keys, value in [(["经营困难", "没钱", "资金紧张"], "公司经营困难"),
                                (["绩效", "考核"], "以绩效为由扣发"),
                                (["离职后", "离职时", "没结清"], "离职后未结清"),
                                (["无故", "就是不发", "拖着"], "无故拖欠")]:
                if any(k in text for k in keys):
                    put("wage_reason", value)
                    break
        if available("wage_evidence"):
            for keys, value in [(["工资条"], "工资条"), (["银行流水", "流水"], "银行流水"),
                                (["微信", "支付宝", "转账"], "微信/支付宝转账"),
                                (["考勤"], "考勤记录"), (["没有证据", "没证据"], "没有书面证据")]:
                if any(k in text for k in keys):
                    put("wage_evidence", value)
                    break
        if available("reduced_salary") and re.search(r"降薪|降工资|调薪|减薪", text):
            put("reduced_salary", "没有被降薪" if re.search(r"没有|没被|未", text) else "被降薪")
        if available("wage_period"):
            m = re.search(r"(\d{4}\s*年\s*\d{1,2}\s*月(?:\s*(?:至|到|-)\s*\d{1,2}\s*月)?)", text)
            if m:
                put("wage_period", m.group(1))
            else:
                m = re.search(r"(?:欠|拖|没发|未发|少发)[^。；]{0,10}?(" + CN_INT + r")\s*个?月", text)
                if m:
                    put("wage_period", m.group(1) + "个月")

        # ---- overtime --------------------------------------------------
        if available("overtime_exists") and re.search(r"加班|996|大小周|单休", text):
            put("overtime_exists", "没有" if re.search(r"不加班|没有加班|从不加班", text) else "有")
        if available("work_schedule"):
            if "综合工时" in text or "综合计算工时" in text:
                put("work_schedule", "综合计算工时")
            elif "不定时" in text:
                put("work_schedule", "不定时工时")
            elif "标准工时" in text or "朝九晚五" in text:
                put("work_schedule", "标准工时")
        for key, cue in [("overtime_hours_weekday", r"工作日|平时|每天"),
                         ("overtime_hours_rest", r"周末|休息日|周六|周日"),
                         ("overtime_hours_holiday", r"法定节假日|节假日|国庆|春节")]:
            if available(key):
                m = re.search(r"(?:" + cue + r")[^。；]{0,10}?(\d+(?:\.\d+)?)\s*小时", text)
                if m:
                    put(key, float(m.group(1)))
        if available("overtime_paid"):
            if re.search(r"没(有)?(发|给|支付).{0,4}加班费|没有加班费", text):
                put("overtime_paid", "没有支付")
            elif re.search(r"发了?加班费|给了?加班费", text):
                put("overtime_paid", "支付了")
        if available("overtime_evidence"):
            for keys, value in [(["打卡", "考勤"], "考勤打卡"), (["排班"], "排班表"),
                                (["工作群", "微信", "钉钉"], "工作群消息"),
                                (["审批"], "加班审批单"), (["没有证据", "没证据"], "没有证据")]:
                if any(k in text for k in keys):
                    put("overtime_evidence", value)
                    break

        # ---- contract / probation -------------------------------------
        if available("contract_signed"):
            if re.search(r"(?:合同|文本).{0,4}没给我|没给我(?:合同|一份|文本)|没拿到合同", text):
                put("contract_signed", "签了但没给我")
            elif re.search(r"没.{0,6}签(?!收|字)|未.{0,6}签(?!收|字)|不签|无合同|没有合同", text):
                put("contract_signed", "未签书面合同")
            elif re.search(r"签了|签过|签了合同|有合同", text):
                put("contract_signed", "已签书面合同")
        if available("no_contract_months"):
            m = re.search(r"(" + CN_INT + r")\s*个?月.{0,6}(?:没签|未签|没合同)|"
                          r"(?:没签|未签).{0,6}(" + CN_INT + r")\s*个?月", text)
            if m:
                n = _int(m.group(1) or m.group(2))
                if n:
                    put("no_contract_months", float(n))
        if available("probation"):
            put("probation", "有试用期" if "试用期" in text else ("没有试用期" if re.search(r"没有试用期|无试用期", text) else None))
        if available("probation_length"):
            m = re.search(r"试用期[^。；]{0,8}?(" + CN_INT + r")\s*个?月", text)
            if m:
                n = _int(m.group(1))
                if n:
                    put("probation_length", float(n))
        if available("illegal_probation"):
            for keys, value in [(["超过", "超期"], "试用期超过法定上限"),
                                (["低于80%", "八折", "打八折"], "试用期工资低于80%"),
                                (["只签试用期"], "只签试用期合同")]:
                if any(k in text for k in keys):
                    put("illegal_probation", value)
                    break
        if available("contract_terms_changed") and re.search(r"调岗|降薪|换岗|变更", text):
            put("contract_terms_changed", "被单方变更")
        if available("contract_type"):
            if "无固定期限" in text:
                put("contract_type", "无固定期限")
            elif "固定期限" in text:
                put("contract_type", "固定期限")
        if available("contract_copies"):
            if re.search(r"两份都在公司|没给我一份|没给我(?:合同|文本)", text):
                put("contract_copies", "没有给我")
            elif re.search(r"我有一份|给了我一份", text):
                put("contract_copies", "我有一份")

        # ---- work injury ----------------------------------------------
        if available("injury_at_work"):
            if re.search(r"上下班途中|下班路上|上班路上", text):
                put("injury_at_work", "上下班途中交通事故")
            elif re.search(r"职业病", text):
                put("injury_at_work", "职业病")
            elif re.search(r"因工外出|出差", text):
                put("injury_at_work", "因工外出")
            elif re.search(r"工作时间|工作场所|上班时|干活时|车间|工地", text):
                put("injury_at_work", "工作时间和场所内")
        if available("injury_reported"):
            if re.search(r"单位.{0,6}(申请|报)", text):
                put("injury_reported", "单位30日内申请")
            elif re.search(r"自己.{0,6}申请|我.{0,4}申请", text):
                put("injury_reported", "自己1年内申请")
            elif re.search(r"没申请|还没申请|没有申请", text):
                put("injury_reported", "还没申请")
        if available("injury_recognized"):
            if re.search(r"认定.{0,4}工伤|工伤认定.{0,4}(下来|通过)", text):
                put("injury_recognized", "已认定工伤")
            elif re.search(r"没认定|未认定|不认定", text):
                put("injury_recognized", "认定被驳回")
        if available("disability_level"):
            m = re.search(r"([一二三四五六七八九十])\s*级", text)
            if m:
                put("disability_level", m.group(1) + "级")
        if available("work_injury_insurance"):
            if re.search(r"没(有)?(参加|交|缴).{0,4}工伤|没参保", text):
                put("work_injury_insurance", "没有参加")
            elif re.search(r"参加了?工伤|有工伤险|交了工伤", text):
                put("work_injury_insurance", "参加了工伤保险")
        if available("injury_evidence"):
            for keys, value in [(["照片", "视频", "监控"], "事故现场照片/视频"),
                                (["证人"], "证人证言"), (["病历", "诊断"], "医院病历"),
                                (["报警"], "报警记录")]:
                if any(k in text for k in keys):
                    put("injury_evidence", value)
                    break

        # ---- social insurance / annual leave ---------------------------
        if available("social_insurance"):
            if re.search(r"断缴|断了", text):
                put("social_insurance", "断缴")
            elif re.search(r"(没|未).{0,8}(交|缴|买).{0,6}社保|社保.{0,8}(没|未).{0,6}(交|缴|买)|"
                           r"没(有)?(交|缴|买)|未缴|不缴", text):
                put("social_insurance", "未缴纳")
            elif re.search(r"最低基数|按最低", text):
                put("social_insurance", "按最低基数缴纳")
            elif re.search(r"正常缴|交了社保|有社保", text):
                put("social_insurance", "正常缴纳")
        if available("housing_fund") and "公积金" in text:
            put("housing_fund", "未缴纳" if re.search(r"没(有)?(交|缴)|未缴", text) else "正常缴纳")
        if available("social_insurance_claim"):
            if re.search(r"补缴", text):
                put("social_insurance_claim", "要求补缴")
            elif re.search(r"赔偿损失|损失", text):
                put("social_insurance_claim", "要求赔偿损失")
            elif re.search(r"被迫解除|经济补偿", text):
                put("social_insurance_claim", "要求被迫解除经济补偿")
        if available("annual_leave_taken"):
            if re.search(r"(?:一天|1天|一天也)?(?:没|未)休|没有休(?:过)?年假|年假.{0,6}(?:没|未)休", text):
                put("annual_leave_taken", 0.0)
            else:
                m = re.search(r"(?:年假|年休假)[^。；]{0,8}?(" + CN_INT + r")\s*天|"
                              r"休了?\s*(" + CN_INT + r")\s*天(?:年假|年休假)", text)
                if m:
                    n = _int(m.group(1) or m.group(2))
                    if n is not None:
                        put("annual_leave_taken", float(n))
        if available("cumulative_work_years"):
            m = re.search(r"(?:工作|干了|工龄)[^。；]{0,6}?(" + CN_INT + r")\s*年", text)
            if m:
                n = _int(m.group(1))
                if n is not None:
                    put("cumulative_work_years", float(n))
        if available("annual_leave_paid"):
            if re.search(r"没(有)?(给|支付).{0,4}(年假|300%)", text):
                put("annual_leave_paid", "没有支付")
            elif re.search(r"支付了?年假|给了?300%", text):
                put("annual_leave_paid", "支付了")

        # ---- noncompete ------------------------------------------------
        if available("noncompete_signed") and re.search(r"竞业", text):
            put("noncompete_signed", "没有签" if re.search(r"没签|未签", text) else "签了竞业限制协议")
        if available("noncompete_months"):
            m = re.search(r"竞业[^。；]{0,10}?(" + CN_INT + r")\s*个?月|"
                          r"竞业[^。；]{0,10}?(" + CN_INT + r")\s*年|"
                          r"(" + CN_INT + r")\s*年.{0,4}竞业", text)
            if m:
                n = _int(m.group(1) or m.group(2) or m.group(3))
                if n:
                    months = float(n) if m.group(1) else float(n) * 12
                    put("noncompete_months", months)
        if available("noncompete_paid"):
            if re.search(r"没(有)?(给|支付).{0,4}竞业|不给补偿", text):
                put("noncompete_paid", "没有支付")
            elif re.search(r"按月(给|支付)|每月(给|支付)", text):
                put("noncompete_paid", "按月支付了")
        if available("noncompete_claim"):
            if re.search(r"公司.{0,6}(告|索赔|要).{0,4}违约金", text):
                put("noncompete_claim", "被公司索赔违约金")
            elif re.search(r"解除竞业", text):
                put("noncompete_claim", "要求解除竞业限制")
            elif re.search(r"竞业补偿|要补偿", text):
                put("noncompete_claim", "要求支付补偿")
        if available("new_employer_competitor") and re.search(r"去了?(竞争|同行|对手)", text):
            put("new_employer_competitor", "去了竞争单位")

        # ---- maternity / dispatch -------------------------------------
        if available("maternity_allowance"):
            if re.search(r"生育津贴", text):
                put("maternity_allowance", "领取了生育津贴")
            elif re.search(r"公司发工资|单位发工资", text):
                put("maternity_allowance", "单位发工资")
            elif re.search(r"没发|没有发", text):
                put("maternity_allowance", "没有发")
        if available("maternity_dismissal"):
            if re.search(r"怀孕.{0,6}(辞退|开除|解除)|因为怀孕", text):
                put("maternity_dismissal", "因怀孕/生育被辞退")
            elif re.search(r"降薪|调岗", text):
                put("maternity_dismissal", "被降薪或调岗")
        if available("dispatch_type"):
            if "劳务派遣" in text or "派遣" in text:
                put("dispatch_type", "劳务派遣")
            elif "外包" in text:
                put("dispatch_type", "业务外包")
            elif re.search(r"骑手|网约车|主播|平台", text):
                put("dispatch_type", "平台/新业态用工")
        if available("platform_worker"):
            for keys, value in [(["骑手", "外卖"], "外卖骑手"), (["网约车", "司机"], "网约车司机"),
                                (["主播"], "网络主播")]:
                if any(k in text for k in keys):
                    put("platform_worker", value)
                    break
        if available("work_management"):
            for keys, value in [(["打卡", "考勤"], "打卡考勤"), (["派单"], "平台派单"),
                                (["考核", "绩效"], "绩效考核"), (["不管", "自由", "想干就干"], "没有管理")]:
                if any(k in text for k in keys):
                    put("work_management", value)
                    break
        if available("uniform_tools") and re.search(r"工服|工牌|公司车|平台标识", text):
            put("uniform_tools", "穿工服/用公司工具")

        # ---- procedure -------------------------------------------------
        if available("arbitration_filed") and re.search(r"仲裁", text):
            put("arbitration_filed", "已申请" if re.search(r"申请了|已申请|已经仲裁|提交了", text) else "没有申请")
        if available("court_filed") and re.search(r"起诉|法院", text):
            put("court_filed", "已起诉" if re.search(r"起诉了|已起诉|立案", text) else "没有起诉")
        if available("arbitration_result"):
            for keys, value in [(["已受理", "受理了"], "已受理"), (["裁决", "裁了"], "已裁决"),
                                (["调解"], "调解结案")]:
                if any(k in text for k in keys):
                    put("arbitration_result", value)
                    break
        if available("deadline_aware"):
            if re.search(r"过了一年|超过一年|一年多了|时效.*过", text):
                put("deadline_aware", "知道，可能已经过了")

        # ---- tort (kept from v1) --------------------------------------
        if available("responsibility"):
            if re.search(r"对方全责|他全责|全责", text):
                put("responsibility", "对方全责")
            elif re.search(r"主要责任|主责", text):
                put("responsibility", "对方主要责任")
            elif re.search(r"同等责任|各一半", text):
                put("responsibility", "同等责任")
            elif re.search(r"次要责任|次责", text):
                put("responsibility", "对方次要责任")
            elif re.search(r"还没认定|未认定|没有认定书", text):
                put("responsibility", "尚未认定")
        if available("injury") and not available("injury_at_work"):
            if re.search(r"死亡|去世|身亡", text):
                put("injury", "死亡")
            elif re.search(r"[一二三四五六七八九十]级伤残|伤残等级", text):
                put("injury", "已鉴定伤残等级")
            elif re.search(r"伤残|残疾", text):
                put("injury", "伤残但未鉴定")
            elif re.search(r"重伤", text):
                put("injury", "重伤")
            elif re.search(r"轻伤|擦伤|一般伤", text):
                put("injury", "一般伤害")
        if available("residence"):
            if re.search(r"农村|农业户口", text):
                put("residence", "农村")
            elif re.search(r"城镇|城市户口|非农业", text):
                put("residence", "城镇")
        if available("insurance") and re.search(r"保险|交强险|三者险|商业险", text):
            if re.search(r"没有保险|没保险|未投保", text):
                put("insurance", "没有保险")
            elif re.search(r"交强险和商业|商业三者险", text):
                put("insurance", "交强险和商业险")
            elif re.search(r"交强险", text):
                put("insurance", "仅有交强险")
        if available("employment") and re.search(r"上班|工作|送货|公司车|办公事|职务", text):
            put("employment", "执行工作任务" if not re.search(r"私事|下班", text) else "个人事务")

        unknown = [k for k, v in found.items() if v in ("记不清", "不知道")]
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
                f = self.schema.field(ctype, key) if ctype else None
                if not f:
                    f = self.schema.field_any(key)
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
