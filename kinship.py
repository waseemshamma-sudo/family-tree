# -*- coding: utf-8 -*-
"""
kinship.py — تسمية صلة القرابة بدقة (بدل كلمة "قريب").

a = عدد الأجيال من الشخص الأول صعوداً حتى الجد المشترك
b = عدد الأجيال من الشخص الثاني صعوداً حتى الجد المشترك

الشجرة تعتمد على الأب فقط (father_id) لذلك تغطي القرابة من جهة الأب.
إن أُضيف عمود gender (ذكر/أنثى) تتحول المسميات تلقائياً (أخت، عمة، ابنة عم ...).
"""

_ORD = {1: 'الأول', 2: 'الثاني', 3: 'الثالث', 4: 'الرابع', 5: 'الخامس',
        6: 'السادس', 7: 'السابع', 8: 'الثامن', 9: 'التاسع', 10: 'العاشر'}


_ORD_F = {1: 'الأولى', 2: 'الثانية', 3: 'الثالثة', 4: 'الرابعة', 5: 'الخامسة',
          6: 'السادسة', 7: 'السابعة', 8: 'الثامنة', 9: 'التاسعة', 10: 'العاشرة'}


def ordinal(n):
    return _ORD.get(n, str(n))


def ordinal_f(n):
    return _ORD_F.get(n, str(n))


def is_female(g):
    return str(g or '').strip().lower() in ('f', 'female', 'أنثى', 'انثى', 'بنت', 'امرأة')


def ancestor_name(n):
    """اسم الجد الذي يعلو n جيلاً."""
    return {1: 'الأب', 2: 'الجد', 3: 'أبو الجد', 4: 'جد الجد'}.get(n, f'الجد {ordinal(n)}')


def descendant_name(n):
    """اسم النسل الذي ينزل n جيلاً."""
    return {1: 'ابن', 2: 'حفيد', 3: 'ابن حفيد', 4: 'حفيد الحفيد'}.get(n, f'حفيد من الجيل {n}')


def _degree(k):
    return '' if k == 1 else f' من الدرجة {ordinal_f(k)}'


def _feminize(label):
    for male, fem in (('ابن', 'ابنة'), ('حفيد', 'حفيدة'), ('أخ', 'أخت'), ('عم', 'عمة')):
        if label.startswith(male):
            return fem + label[len(male):]
    return label


def relation_label(a, b, female=False):
    """مسمى الشخص الأول بالنسبة للثاني."""
    if a == 0 and b == 0:
        return 'نفس الشخص'
    if a == 0:                                  # الأول جد/أب للثاني
        return ancestor_name(b)
    if b == 0:                                  # الأول ابن/حفيد للثاني
        label = descendant_name(a)
    else:
        k = min(a, b) - 1                       # k=0 إخوة، k=1 أبناء عم ...
        if a == b:
            label = 'أخ' if k == 0 else 'ابن عم' + _degree(k)
        elif a < b:                             # الأول من جيل أعلى
            diff = b - a
            if k == 0:
                label = 'عم' if diff == 1 else f'عم {ancestor_name(diff - 1)}'
            else:
                label = f'ابن عم {ancestor_name(diff)}' + _degree(k)
        else:                                   # الأول من جيل أدنى
            diff = a - b
            if k == 0:
                label = f'{descendant_name(diff)} الأخ'
            else:
                label = f'{descendant_name(diff)} ابن العم' + _degree(k)
    return _feminize(label) if female else label


def category(a, b):
    if a == 0 or b == 0:
        return 'قرابة مباشرة (أصول وفروع)'
    if a == b == 1:
        return 'إخوة'
    if min(a, b) == 1:
        return 'أعمام وأبناء إخوة'
    return 'أبناء عمومة'


def gen_word(n):
    return {1: 'جيل واحد', 2: 'جيلان'}.get(n, f'{n} أجيال' if n <= 10 else f'{n} جيلاً')


def explain(name1, name2, anc_name, a, b):
    if a == 0:
        return f'{name1} هو الأصل الذي ينحدر منه {name2}، وبينهما {gen_word(b)}.'
    if b == 0:
        return f'{name2} هو الأصل الذي ينحدر منه {name1}، وبينهما {gen_word(a)}.'
    return (f'يلتقي نسبهما عند {anc_name}؛ بينه وبين {name1} {gen_word(a)}،'
            f' وبينه وبين {name2} {gen_word(b)}.')
