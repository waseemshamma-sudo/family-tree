# -*- coding: utf-8 -*-
"""
tree_pdf.py — رسم شجرة العائلة كملف PDF (مخطط شجري حقيقي بخطوط وصل).

الاستخدام:
    from tree_pdf import build_tree_pdf
    pdf_bytes = build_tree_pdf(members, root_id=5, generations=0,
                               layout='auto', paper='auto', details=True)

المتطلبات: reportlab, arabic-reshaper, python-bidi
والخطوط: static/fonts/Amiri-Regular.ttf و Amiri-Bold.ttf
"""
import io
import os
import re
from datetime import datetime

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'fonts')
F_REG, F_BOLD = 'Amiri', 'Amiri-Bold'
_fonts_ready = False

# (لون الحدود/الخط الداكن، لون التعبئة الفاتح) لكل جيل
PALETTE = [
    ('#1b5e20', '#e8f5e9'), ('#0d47a1', '#e3f2fd'), ('#e65100', '#fff3e0'),
    ('#6a1b9a', '#f3e5f5'), ('#00695c', '#e0f2f1'), ('#ad1457', '#fce4ec'),
    ('#4e342e', '#efebe9'), ('#37474f', '#eceff1'),
]
BRANCH_COLOR = '#7a5c3e'     # لون الأغصان
MAX_PAGE = 14000             # حد برنامج Acrobat ~14400 نقطة


# ------------------------------------------------------------------ أدوات
def _ensure_fonts():
    global _fonts_ready
    if _fonts_ready:
        return
    reg = os.path.join(FONT_DIR, 'Amiri-Regular.ttf')
    bold = os.path.join(FONT_DIR, 'Amiri-Bold.ttf')
    if not (os.path.exists(reg) and os.path.exists(bold)):
        raise FileNotFoundError(
            'ملفات الخط غير موجودة. ضع Amiri-Regular.ttf و Amiri-Bold.ttf في static/fonts/')
    pdfmetrics.registerFont(TTFont(F_REG, reg))
    pdfmetrics.registerFont(TTFont(F_BOLD, bold))
    _fonts_ready = True


def ar(text):
    """تشكيل الحروف العربية + ترتيب الاتجاه ليظهر صحيحاً في PDF."""
    return get_display(arabic_reshaper.reshape(str(text)))


def year_of(value):
    if not value:
        return None
    m = re.search(r'\d{4}', str(value))
    return int(m.group()) if m else None


def _is_female(g):
    return str(g or '').strip().lower() in ('f', 'female', 'أنثى', 'انثى', 'بنت', 'امرأة')


class _N:
    __slots__ = ('id', 'name', 'birth', 'death', 'female', 'children', 'vis',
                 'depth', 'slot', 'hidden', 'virtual', 'x', 'y')

    def __init__(self, m=None):
        self.virtual = m is None
        self.id = m['id'] if m else 0
        self.name = (m.get('name') or '').strip() if m else ''
        self.birth = year_of(m.get('birth_year')) if m else None
        self.death = year_of(m.get('death_year')) if m else None
        self.female = _is_female(m.get('gender')) if m else False
        if m and self.death is None and m.get('death_year'):
            self.death = -1                       # متوفى بدون سنة معروفة
        self.children, self.vis, self.hidden = [], [], 0
        self.depth = self.slot = 0
        self.x = self.y = 0.0


def _sort_key(n):
    return (n.birth if n.birth else 9999, n.id)


def _build_forest(members):
    nodes = {m['id']: _N(m) for m in members}
    parent = {}
    for m in members:
        f = m.get('father_id')
        parent[m['id']] = f if (f and f in nodes and f != m['id']) else None
    # كسر الحلقات المغلقة في البيانات (أب هو ابن لابنه...)
    for pid in list(parent):
        seen, cur = set(), pid
        while cur is not None and cur not in seen:
            seen.add(cur)
            cur = parent.get(cur)
        if cur is not None:                       # عدنا لعقدة زرناها = حلقة
            parent[cur] = None
    roots = []
    for pid, f in parent.items():
        (nodes[f].children if f else roots).append(nodes[pid])
    for n in nodes.values():
        n.children.sort(key=_sort_key)
    roots.sort(key=_sort_key)
    return nodes, parent, roots


def _count_desc(n):
    return sum(1 + _count_desc(c) for c in n.children)


def _lineage(parent, nodes, rid, limit=8):
    names, cur = [], rid
    while cur is not None and len(names) < limit:
        names.append(nodes[cur].name)
        cur = parent.get(cur)
    if not names:
        return ''
    first = 'بنت' if nodes[rid].female else 'بن'
    return names[0] + ''.join(f' {first if i == 0 else "بن"} {n}' for i, n in enumerate(names[1:]))


# ------------------------------------------------------------------ التخطيط
def _assign(n, depth, counter, gens):
    n.depth = depth
    show = n.children if (gens == 0 or depth + 1 < gens) else []
    n.vis = show
    n.hidden = _count_desc(n) if (n.children and not show) else 0
    if not show:
        n.slot = counter[0]
        counter[0] += 1
    else:
        for k in show:
            _assign(k, depth + 1, counter, gens)
        n.slot = (show[0].slot + show[-1].slot) / 2.0


def _walk(n):
    yield n
    for k in n.vis:
        yield from _walk(k)


# ------------------------------------------------------------------ الرسم
def build_tree_pdf(members, root_id=None, generations=0, layout='auto',
                   paper='auto', details=True, title='شجرة عائلة شما'):
    """
    members     : قائمة قواميس (id, name, father_id, birth_year, death_year, gender اختياري)
    root_id     : رقم الشخص الذي يبدأ منه الفرع (None = الشجرة كاملة)
    generations : عدد الأجيال المعروضة من الجذر (0 = الكل)
    layout      : 'v' رأسي كالشجرة التقليدية | 'h' أفقي مضغوط | 'auto'
    paper       : 'auto' مقاس مخصص يناسب الشجرة | 'A4' | 'A3'
    """
    _ensure_fonts()
    nodes, parent, roots = _build_forest(members)

    if root_id is not None:
        if root_id not in nodes:
            raise ValueError('الشخص غير موجود')
        top = _N()
        top.children = [nodes[root_id]]
        sub = nodes[root_id].name
    else:
        top = _N()
        top.children = roots
        sub = ''
    gens = max(0, int(generations or 0))

    counter = [0]
    _assign(top, -1, counter, gens)
    leaves = max(counter[0], 1)
    vis = [n for n in _walk(top) if not n.virtual]
    if not vis:
        raise ValueError('لا توجد بيانات لرسمها')
    max_depth = max(n.depth for n in vis)

    # ---- أبعاد البطاقات
    f_name = 10.5
    longest = max(pdfmetrics.stringWidth(ar(n.name), F_BOLD, f_name) for n in vis)
    node_w = min(max(longest + 20, 70), 128)
    has_detail = details and any(n.birth or n.death for n in vis)
    node_h = 34 if has_detail else 24

    if layout not in ('v', 'h'):
        layout = 'v' if leaves <= 28 else 'h'

    v_gap, h_gap = 46, 14          # رأسي: بين الأجيال / بين الإخوة
    lvl_gap, row_gap = 48, 9       # أفقي: بين الأجيال / بين الصفوف

    if layout == 'v':
        cell = node_w + h_gap
        cw = leaves * cell - h_gap
        ch = (max_depth + 1) * node_h + max_depth * v_gap
        for n in vis:
            cx = cw - ((n.slot + 0.5) * cell - h_gap / 2.0)      # RTL: الأكبر يميناً
            n.x, n.y = cx - node_w / 2.0, n.depth * (node_h + v_gap)
    else:
        cell = node_h + row_gap
        ch = leaves * cell - row_gap
        cw = (max_depth + 1) * node_w + max_depth * lvl_gap
        for n in vis:
            n.x = cw - node_w - n.depth * (node_w + lvl_gap)     # الجذر يميناً
            n.y = (n.slot + 0.5) * cell - row_gap / 2.0 - node_h / 2.0

    # ---- حجم الصفحة
    margin, head_h, foot_h = 28, 118, 54
    if paper in ('A4', 'A3'):
        from reportlab.lib.pagesizes import A3, A4, landscape
        base = A4 if paper == 'A4' else A3
        page_w, page_h = landscape(base) if cw > ch else base
        area_w, area_h = page_w - 2 * margin, page_h - head_h - foot_h - margin
        scale = min(area_w / cw, area_h / ch, 1.6)
    else:
        scale = min(1.0, (MAX_PAGE - 2 * margin) / cw,
                    (MAX_PAGE - head_h - foot_h - margin) / ch)
        page_w = max(cw * scale + 2 * margin, 560)
        page_h = ch * scale + head_h + foot_h + margin
        area_w, area_h = page_w - 2 * margin, page_h - head_h - foot_h - margin

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    c.setTitle(title + (f' - {sub}' if sub else ''))
    c.setAuthor('شجرة عائلة شما')

    # ---- الترويسة
    c.setFillColor(HexColor('#1b5e20'))
    c.rect(0, page_h - 58, page_w, 58, stroke=0, fill=1)
    c.setFillColor(HexColor('#c8a24a'))
    c.rect(0, page_h - 61, page_w, 3, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont(F_BOLD, 24)
    c.drawCentredString(page_w / 2, page_h - 40, ar(title))
    c.setFillColor(HexColor('#2c3e50'))
    if sub:
        c.setFont(F_BOLD, 15)
        c.drawCentredString(page_w / 2, page_h - 86, ar('فرع: ' + sub))
        lin = _lineage(parent, nodes, root_id)
        c.setFont(F_REG, 10)
        c.setFillColor(HexColor('#666666'))
        c.drawCentredString(page_w / 2, page_h - 104, ar('النسب: ' + lin))
    else:
        c.setFont(F_BOLD, 14)
        c.drawCentredString(page_w / 2, page_h - 90, ar('الشجرة الكاملة'))

    # إطار خفيف
    c.setStrokeColor(HexColor('#c8a24a'))
    c.setLineWidth(1)
    c.rect(10, 10, page_w - 20, page_h - 20 - 61, stroke=1, fill=0)

    # ---- منطقة الرسم (توسيط)
    ox = margin + (area_w - cw * scale) / 2.0
    top_y = page_h - head_h - (area_h - ch * scale) / 2.0      # أعلى نقطة للمحتوى

    def px(x):
        return ox + x * scale

    def py(y):
        return top_y - y * scale

    # ---- الأغصان (خطوط الوصل)
    c.setLineCap(1)
    c.setLineJoin(1)
    c.setStrokeColor(HexColor(BRANCH_COLOR))
    for n in vis:
        if not n.vis:
            continue
        c.setLineWidth(max(0.9, 2.8 - 0.35 * n.depth) * max(scale, 0.5))
        kids = n.vis
        if layout == 'v':
            sx, sy = px(n.x + node_w / 2), py(n.y + node_h)
            my = py(n.y + node_h + v_gap / 2.0)
            xs = [px(k.x + node_w / 2) for k in kids]
            c.line(sx, sy, sx, my)
            c.line(min(xs + [sx]), my, max(xs + [sx]), my)
            for k, kx in zip(kids, xs):
                c.line(kx, my, kx, py(k.y))
        else:
            sx, sy = px(n.x), py(n.y + node_h / 2)
            mx = px(n.x - lvl_gap / 2.0)
            ys = [py(k.y + node_h / 2) for k in kids]
            c.line(sx, sy, mx, sy)
            c.line(mx, min(ys + [sy]), mx, max(ys + [sy]))
            for k, ky in zip(kids, ys):
                c.line(mx, ky, px(k.x + node_w), ky)

    # ---- البطاقات
    for n in vis:
        dark, light = PALETTE[n.depth % len(PALETTE)]
        x, y = px(n.x), py(n.y + node_h)           # الزاوية السفلية اليسرى
        w, h = node_w * scale, node_h * scale
        root_card = n.depth == 0
        c.setLineWidth(1.3 * max(scale, 0.6))
        c.setStrokeColor(HexColor(dark))
        c.setFillColor(HexColor(dark) if root_card else HexColor('#f1f1f1' if n.death else light))
        c.setDash(3, 2) if n.death else c.setDash()
        c.roundRect(x, y, w, h, 7 * scale, stroke=1, fill=1)
        c.setDash()

        # اسم الشخص (تصغير تلقائي ليتسع داخل البطاقة)
        txt = ar(n.name)
        fs = f_name * scale
        avail = w - 8 * scale
        while pdfmetrics.stringWidth(txt, F_BOLD, fs) > avail and fs > 5.5 * scale:
            fs -= 0.25
        c.setFillColor(white if root_card else HexColor('#1f2d3d'))
        c.setFont(F_BOLD, fs)
        line2 = ''
        if has_detail:
            if n.birth and n.death and n.death > 0:
                line2 = f'{n.birth} - {n.death}'
            elif n.birth and n.death:
                line2 = f'{n.birth} - ؟'
            elif n.birth:
                line2 = f'{n.birth}'
            elif n.death and n.death > 0:
                line2 = f'- {n.death}'
        if line2:
            c.drawCentredString(x + w / 2, y + h * 0.56, txt)
            c.setFont(F_REG, 7.5 * scale)
            c.setFillColor(HexColor('#ffffffcc') if root_card else HexColor('#5d6d7e'))
            c.drawCentredString(x + w / 2, y + h * 0.17, ar(line2))
        else:
            c.drawCentredString(x + w / 2, y + h / 2 - fs * 0.32, txt)

        # عدد الفروع المخفية بسبب حد الأجيال
        if n.hidden:
            r = 8.5 * max(scale, 0.7)
            bx = x + w / 2 if layout == 'v' else x
            by = y if layout == 'v' else y + h / 2
            c.setFillColor(HexColor('#c8a24a'))
            c.setStrokeColor(white)
            c.setLineWidth(1)
            c.circle(bx, by, r, stroke=1, fill=1)
            c.setFillColor(white)
            c.setFont(F_BOLD, r * 0.95)
            c.drawCentredString(bx, by - r * 0.32, f'+{n.hidden}')

    # ---- التذييل: مفتاح الألوان + المعلومات
    ly = 30
    items = [(PALETTE[d % len(PALETTE)], f'الجيل {d + 1}') for d in range(max_depth + 1)][:8]
    c.setFont(F_REG, 8.5)
    total_w = sum(pdfmetrics.stringWidth(ar(t), F_REG, 8.5) + 26 for _, t in items) + 90
    cur = (page_w + total_w) / 2.0
    for (dark, light), t in items:
        c.setFillColor(HexColor(light))
        c.setStrokeColor(HexColor(dark))
        c.setLineWidth(1)
        c.roundRect(cur - 14, ly - 3, 14, 10, 3, stroke=1, fill=1)
        c.setFillColor(HexColor('#444444'))
        wt = pdfmetrics.stringWidth(ar(t), F_REG, 8.5)
        c.drawRightString(cur - 18, ly, ar(t))
        cur -= wt + 34
    c.setStrokeColor(HexColor('#555555'))
    c.setFillColor(HexColor('#f1f1f1'))
    c.setDash(3, 2)
    c.roundRect(cur - 14, ly - 3, 14, 10, 3, stroke=1, fill=1)
    c.setDash()
    c.setFillColor(HexColor('#444444'))
    c.drawRightString(cur - 18, ly, ar('متوفى'))

    c.setFont(F_REG, 8)
    c.setFillColor(HexColor('#888888'))
    stamp = datetime.now().strftime('%Y-%m-%d')
    c.drawCentredString(page_w / 2, 16, ar(f'عدد الأشخاص في المخطط: {len(vis)}   •   تاريخ الإصدار: {stamp}'))

    c.showPage()
    c.save()
    return buf.getvalue()
