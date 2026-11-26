"""Small, dependency-free text utilities for the DLawBench adapter.

Everything here is intentionally simple and deterministic: the evaluation must
be reproducible offline, and the shim must never depend on an LLM.
"""
from __future__ import annotations

import re

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_WORD_RUN = re.compile(r"[a-zA-Z][a-zA-Z0-9_.+-]*|\d+(?:\.\d+)?")
_SENT_SPLIT = re.compile(r"[。！？!?；;\n]+")
_DATE_PATTERNS = [
    re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日"),
    re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月"),
    re.compile(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"),
    re.compile(r"\d{4}[-/.]\d{1,2}"),
]
_AMOUNT = re.compile(r"\d+(?:\.\d+)?\s*(?:万|亿)?\s*元")

# Bigrams that carry no discriminative meaning in legal Chinese.  Kept short on
# purpose: over-filtering would erase legal terms such as "应当" or "规定".
STOP_BIGRAMS = {
    "我们", "你们", "他们", "这个", "那个", "什么", "怎么", "现在", "就是",
    "可以", "没有", "不是", "还是", "因为", "所以", "但是", "如果", "已经",
    "一个", "一些", "这些", "那些", "自己", "事情", "问题", "进行", "相关",
    "以及", "或者", "并且", "对于", "关于", "通过", "根据", "按照", "认为",
    "觉得", "知道", "需要", "应该", "可能", "一直", "后来", "然后", "当时",
    "律师", "您好", "你好", "之前", "电话", "看看", "帮忙", "咨询", "请问",
}


def normalize(text: str) -> str:
    """Normalise whitespace and full-width punctuation without changing words."""
    text = (text or "").replace("\u3000", " ")
    text = text.replace("，", ",").replace("。", ".").replace("；", ";")
    text = text.replace("：", ":").replace("（", "(").replace("）", ")")
    text = text.replace("“", '"').replace("”", '"')
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def runs(text: str) -> list[str]:
    """Contiguous CJK / ASCII token runs (order preserved)."""
    return _CJK_RUN.findall(text or "") + _WORD_RUN.findall(text or "")


def bigrams(text: str) -> list[str]:
    """CJK character bigrams plus lower-cased ASCII words."""
    out: list[str] = []
    for run in runs(text or ""):
        if run.isascii():
            out.append(run.lower())
        else:
            for i in range(len(run) - 1):
                out.append(run[i:i + 2])
    return out


def terms(text: str) -> set[str]:
    return {t for t in bigrams(text) if t not in STOP_BIGRAMS}


def containment(needle: str | set[str], haystack: str | set[str]) -> float:
    """Fraction of *needle* terms present in *haystack* (0..1)."""
    a = needle if isinstance(needle, set) else terms(needle)
    b = haystack if isinstance(haystack, set) else terms(haystack)
    if not a:
        return 0.0
    return len(a & b) / len(a)


def overlap(needle: str | set[str], haystack: str | set[str]) -> float:
    """Fraction of the smaller term set shared by both sides (0..1)."""
    a = needle if isinstance(needle, set) else terms(needle)
    b = haystack if isinstance(haystack, set) else terms(haystack)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT_SPLIT.split(text or "")]
    return [p for p in parts if len(p) >= 2]


def dates(text: str) -> list[str]:
    found: list[str] = []
    for pattern in _DATE_PATTERNS:
        found.extend(m.group(0) for m in pattern.finditer(text or ""))
    return found


def amounts(text: str) -> list[str]:
    return [m.group(0) for m in _AMOUNT.finditer(text or "")]


def numbers(text: str) -> set[str]:
    """Digits appearing in a text, with separators removed."""
    return {re.sub(r"[^\d.]", "", m.group(0)) for m in re.finditer(r"\d[\d,.]*", text or "")}


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = re.sub(r"\s+", "", item)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def truncate(text: str, limit: int = 220) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


# ── topic detection ────────────────────────────────────────────────────────
TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "time": ("时间", "日期", "哪年", "哪天", "什么时候", "多久", "几月", "几点", "先后", "顺序",
             "经过", "当晚", "当天", "凌晨", "上午", "下午", "晚上"),
    "process": ("发生", "经过", "当时", "现场", "怎么", "如何", "过程", "起因", "冲突", "事故",
                "撞", "驾驶", "行驶", "逆行", "超速", "受伤", "殴打", "拿走", "转入", "签"),
    "role": ("角色", "作用", "负责", "分工", "参与", "地位", "主犯", "从犯", "决定", "指挥", "安排"),
    "evidence": ("证据", "材料", "记录", "聊天", "微信", "录音", "合同", "协议", "票据", "流水",
                 "证人", "监控", "鉴定", "原件", "书面", "通知", "回执", "截图", "录像", "账簿"),
    "amount": ("金额", "钱", "款", "赔偿", "损失", "数额", "工资", "费用", "多少", "计算", "计核",
               "流水", "发票", "补偿", "税额", "货值", "提成", "获利", "租金", "押金"),
    "prior": ("报警", "自首", "到案", "投案", "拘留", "逮捕", "起诉", "判决", "仲裁", "协商",
              "调解", "复议", "上诉", "申诉", "抓获", "传唤", "羁押", "取保"),
    "demand": ("诉求", "希望", "想要", "目标", "结果", "怎么处理", "怎么办", "要求", "主张"),
    "relationship": ("关系", "主体", "公司", "个人", "夫妻", "雇佣", "代理", "股东", "法定代表人",
                     "用工", "劳动关系", "车", "货车", "司机", "老板", "雇主", "挂靠", "承包"),
    "official": ("公安", "法院", "检察", "行政机关", "处罚", "复议", "程序", "执法", "立案",
                 "告知", "送达", "管辖", "认定书", "交警", "派出所", "看守所", "海关"),
    "medical": ("伤", "医院", "治疗", "鉴定", "伤残", "病历", "住院", "手术", "护理", "误工"),
    "family": ("家庭", "孩子", "父母", "经济状况", "收入", "职业", "前科", "户籍", "居住"),
    "contract": ("合同", "条款", "约定", "履行", "违约", "解除", "押金", "租金", "买卖", "租赁"),
    "conduct": ("超载", "超速", "疲劳", "酒驾", "醉驾", "手机", "闯红灯", "逆行", "变道",
                "逃逸", "动手", "殴打", "持械", "威胁"),
    "confession": ("自首", "如实", "供述", "认罪", "认罚", "投案", "坦白", "立功"),
    "compensation": ("赔偿", "谅解", "和解", "垫付", "保险", "退赔", "退赃", "补缴", "罚金"),
    "mitigation": ("前科", "家庭", "抚养", "赡养", "身体", "疾病", "困难", "初犯", "偶犯"),
}


TOPIC_LABELS = {
    "time": "时间线",
    "process": "事情经过",
    "role": "角色分工",
    "evidence": "证据材料",
    "amount": "金额与损失",
    "prior": "此前程序",
    "demand": "诉求",
    "relationship": "主体关系",
    "official": "办案机关",
    "medical": "伤情医疗",
    "family": "个人与家庭情况",
    "contract": "合同约定",
    "conduct": "行为细节",
    "confession": "供述与认罪",
    "compensation": "赔偿与谅解",
    "mitigation": "个人情况",
}


def topics_of(text: str) -> set[str]:
    text = text or ""
    hits: set[str] = set()
    if dates(text):
        hits.add("time")
    for topic, words in TOPIC_KEYWORDS.items():
        for word in words:
            if word in text:
                hits.add(topic)
                break
    return hits


def topic_labels(text_or_topics) -> list[str]:
    topics = text_or_topics if isinstance(text_or_topics, set) else topics_of(text_or_topics)
    return [TOPIC_LABELS[t] for t in TOPIC_KEYWORDS if t in topics]


def topic_overlap(a: str, b: str) -> int:
    return len(topics_of(a) & topics_of(b))
