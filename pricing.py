"""
Pricing engine — calculates live order price step-by-step.
Called from both the API (for real-time updates) and order creation.
"""
from decimal import Decimal
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.models import PricingRule, PaperType, GramOption, Texture, BindingType


@dataclass
class PriceInput:
    paper_type_id:   int | None = None
    gram_option_id:  int | None = None
    texture_id:      int | None = None
    color_mode:      str = "bw"          # 'bw' | 'color'
    copies:          int = 1
    binding_type_id: int | None = None
    discount_pct:    float = 0.0
    page_count:      int = 1             # number of pages/sheets in the file


@dataclass
class PriceBreakdown:
    base_per_page:    Decimal
    paper_multiplier: Decimal
    gram_multiplier:  Decimal
    texture_multiplier: Decimal
    color_multiplier: Decimal
    subtotal_per_copy: Decimal
    copies:           int
    binding_price:    Decimal
    subtotal:         Decimal
    discount_amt:     Decimal
    total:            Decimal
    breakdown_lines:  list[dict]   # human-readable steps for UI


async def calculate_price(inp: PriceInput, db: AsyncSession) -> PriceBreakdown:
    # 1. Base price per page (from pricing_rules)
    rules_result = await db.execute(select(PricingRule).where(PricingRule.name == "default"))
    rules = rules_result.scalar_one()
    base_per_page = Decimal(str(rules.base_price_bw if inp.color_mode == "bw" else rules.base_price_color))

    # 2. Paper multiplier
    paper_mult = Decimal("1.0")
    if inp.paper_type_id:
        pt = await db.get(PaperType, inp.paper_type_id)
        if pt:
            paper_mult = Decimal(str(pt.base_price_multiplier))

    # 3. Gram multiplier
    gram_mult = Decimal("1.0")
    if inp.gram_option_id:
        go = await db.get(GramOption, inp.gram_option_id)
        if go:
            gram_mult = Decimal(str(go.price_multiplier))

    # 4. Texture multiplier
    tex_mult = Decimal("1.0")
    if inp.texture_id:
        tx = await db.get(Texture, inp.texture_id)
        if tx:
            tex_mult = Decimal(str(tx.price_multiplier))

    # 5. Color multiplier (already baked into base_per_page above; mult=1)
    color_mult = Decimal("1.0")

    # 6. Per-copy subtotal
    per_page  = base_per_page * paper_mult * gram_mult * tex_mult
    per_copy  = per_page * inp.page_count
    subtotal_copies = per_copy * inp.copies

    # 7. Binding
    binding_price = Decimal("0.0")
    if inp.binding_type_id:
        bt = await db.get(BindingType, inp.binding_type_id)
        if bt:
            binding_price = Decimal(str(bt.base_price))

    # 8. Subtotal before discount
    subtotal = subtotal_copies + binding_price

    # 9. Discount
    discount_amt = (subtotal * Decimal(str(inp.discount_pct)) / 100).quantize(Decimal("0.01"))
    total = (subtotal - discount_amt).quantize(Decimal("0.01"))

    breakdown_lines = [
        {"label_ar": "سعر الصفحة الأساسي",   "label_en": "Base price/page",    "value": float(base_per_page)},
        {"label_ar": "مضاعف نوع الورق",        "label_en": "Paper type ×",       "value": float(paper_mult)},
        {"label_ar": "مضاعف الجرام",           "label_en": "Gram weight ×",       "value": float(gram_mult)},
        {"label_ar": "مضاعف الملمس",           "label_en": "Texture ×",           "value": float(tex_mult)},
        {"label_ar": f"عدد النسخ × {inp.copies}", "label_en": f"Copies × {inp.copies}", "value": inp.copies},
        {"label_ar": "تغليف",                  "label_en": "Binding",             "value": float(binding_price)},
        {"label_ar": f"خصم {inp.discount_pct}%", "label_en": f"Discount {inp.discount_pct}%", "value": -float(discount_amt)},
        {"label_ar": "الإجمالي",               "label_en": "Total",               "value": float(total)},
    ]

    return PriceBreakdown(
        base_per_page=base_per_page,
        paper_multiplier=paper_mult,
        gram_multiplier=gram_mult,
        texture_multiplier=tex_mult,
        color_multiplier=color_mult,
        subtotal_per_copy=per_copy,
        copies=inp.copies,
        binding_price=binding_price,
        subtotal=subtotal,
        discount_amt=discount_amt,
        total=total,
        breakdown_lines=breakdown_lines,
    )
