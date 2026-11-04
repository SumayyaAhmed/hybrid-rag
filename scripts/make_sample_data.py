"""Generate sample data for a fictional sports store: policy PDFs + an Excel catalogue.

Run:  uv run python scripts/make_sample_data.py
Writes data/pdfs/*.pdf and data/catalogue.xlsx (overwrites them).
"""

import io
from pathlib import Path

import pandas as pd
import pymupdf

DATA = Path(__file__).resolve().parent.parent / "data"
STORE = "Stride Sports"
FOOTER = f"{STORE} Customer Policies - effective 1 March 2026"

# Each policy: title + list of (heading, [paragraphs]). Long enough to spill onto a 2nd page.
POLICIES = {
    "returns_policy.pdf": ("Returns and Refunds Policy", [
        ("Return Window", [
            "You can return most items within 30 days of delivery for a full refund to the original payment method. "
            "Stride Club members get an extended return window of 60 days. The return window starts on the day the "
            "carrier marks your parcel as delivered, not the day you placed the order.",
            "Items must be returned in their original condition with all tags attached and in the original packaging. "
            "Apparel must be unwashed. We cannot accept returns of items that show signs of use, except under the "
            "30-Day Test Run guarantee described below.",
        ]),
        ("30-Day Test Run Guarantee for Running Shoes", [
            "We know you can only judge a running shoe by running in it. Running shoes bought from Stride Sports can be "
            "returned within 30 days even if they have been worn outdoors, as long as they have been used for no more "
            "than 50 km and are not damaged. This guarantee applies once per customer per calendar year.",
            "Hiking boots, trail shoes and casual sneakers are not covered by the Test Run guarantee and must be "
            "returned unworn.",
        ]),
        ("Items That Cannot Be Returned", [
            "For hygiene reasons we cannot accept returns of opened socks, underwear, mouthguards or water bottles "
            "with a broken seal. Items marked Final Sale on the product page cannot be returned or exchanged. "
            "Gift cards are non-refundable.",
        ]),
        ("How to Start a Return", [
            "Log in to your account, open My Orders, choose the item and select Start a Return. You will receive a "
            "prepaid return label by email. Drop the parcel at any partner post office or parcel locker within 14 days "
            "of printing the label. Customers who checked out as a guest can start a return with their order number "
            "and email address on the Returns page.",
            "In-store returns are accepted at every Stride Sports shop. Bring the item and your order confirmation; "
            "store staff can refund you immediately or issue an exchange.",
        ]),
        ("Return Shipping Costs", [
            "Exchanges for a different size or color are free. For refunds, a return shipping fee of 6.95 USD is "
            "deducted from your refund. Returns of faulty or incorrectly delivered items are always free.",
        ]),
        ("Refund Timing", [
            "Once your return reaches our warehouse we inspect it within 2 business days. Approved refunds are sent "
            "to your original payment method and usually appear within 5 to 7 business days, depending on your bank. "
            "Refunds for orders paid with a gift card are returned as store credit.",
            "If your return is rejected because the item is used or damaged, we will email you photos and ship the "
            "item back to you at no cost.",
        ]),
    ]),
    "shipping_policy.pdf": ("Shipping and Delivery Policy", [
        ("Delivery Options", [
            "Standard delivery takes 3 to 5 business days within the continental United States and costs 5.95 USD. "
            "Standard delivery is free on all orders over 75 USD after discounts. Express delivery takes 1 to 2 "
            "business days and costs 14.95 USD regardless of order value.",
            "Next-day delivery is available in selected metro areas for 24.95 USD. Enter your zip code at checkout to "
            "see whether next-day delivery is offered at your address.",
        ]),
        ("Order Cut-Off Times", [
            "Orders placed before 2 pm Eastern Time on a business day are packed and handed to the carrier the same "
            "day. Orders placed after the cut-off, on weekends or on public holidays are dispatched the next business "
            "day. Delivery estimates are counted from the dispatch date.",
        ]),
        ("International Shipping", [
            "We ship to Canada, the United Kingdom and all European Union countries. International delivery takes 7 to "
            "14 business days and costs a flat 19.95 USD. Import duties and local taxes are not included in the price "
            "and are collected by the carrier on delivery. We do not currently ship to Australia, Asia or South America.",
        ]),
        ("Tracking Your Order", [
            "As soon as your parcel leaves our warehouse you will receive an email with a tracking number and a link to "
            "the carrier's tracking page. You can also find tracking details under My Orders in your account. Tracking "
            "information can take up to 24 hours to appear after dispatch.",
        ]),
        ("Lost, Late or Damaged Parcels", [
            "If your tracking has not updated for 5 business days, or your parcel is marked delivered but you cannot "
            "find it, contact our support team. We will open an investigation with the carrier and, if the parcel is "
            "not found within 7 business days, send a free replacement or a full refund.",
            "If your parcel arrives damaged, please take photos of the packaging and the items within 48 hours of "
            "delivery and send them to support. Damaged items are replaced free of charge.",
        ]),
        ("Click and Collect", [
            "You can choose free Click and Collect at checkout and pick up your order from any Stride Sports shop. "
            "Orders are usually ready for collection within 4 hours during opening times. We hold collected orders for "
            "10 days; after that they are returned to the warehouse and refunded.",
        ]),
    ]),
    "warranty_policy.pdf": ("Product Warranty Policy", [
        ("What the Warranty Covers", [
            "All products sold by Stride Sports are covered against manufacturing defects in materials and "
            "workmanship. A manufacturing defect is a fault that exists when the product leaves the factory, such as "
            "a sole separating from the upper, a seam coming apart under normal use, or a zipper that fails.",
        ]),
        ("Warranty Periods", [
            "Footwear is covered for 6 months from the date of purchase. Apparel, socks and bags are covered for 90 "
            "days. Hydration vests and water bottles are covered for 1 year. GPS watches, heart rate monitors and other "
            "electronics are covered for 2 years, including the battery for the first 12 months.",
            "Products bought from the Outlet section carry the same warranty as full-price items.",
        ]),
        ("What the Warranty Does Not Cover", [
            "The warranty does not cover normal wear and tear, such as worn-down outsoles, faded colors or pilling of "
            "fabric. Running shoes that have been used for more than 800 km are considered worn out. Damage caused by "
            "accidents, improper washing, drying on a radiator, or modifications is also not covered.",
            "Water damage to electronics is only covered if the product was used within its stated water resistance "
            "rating. Scratches on watch screens are considered cosmetic and are not covered.",
        ]),
        ("How to Make a Warranty Claim", [
            "Contact our support team with your order number, a short description of the problem and clear photos "
            "showing the defect. Our product specialists review claims within 3 business days. If the claim is "
            "approved we send you a prepaid label so you can return the faulty item free of charge.",
        ]),
        ("Repair, Replacement or Refund", [
            "Depending on the product and the fault, we will repair the item, replace it with the same product, or, if "
            "the product is no longer available, offer a similar product or a full refund. Replacement items carry the "
            "remaining part of the original warranty period, or 90 days, whichever is longer.",
        ]),
        ("Manufacturer Warranties", [
            "Some brands, including PacerPro electronics, offer their own manufacturer warranty in addition to ours. "
            "You may claim under either warranty. Our support team can help you contact the manufacturer directly.",
        ]),
    ]),
    "privacy_policy.pdf": ("Privacy Policy", [
        ("Information We Collect", [
            "When you create an account or place an order we collect your name, email address, phone number, delivery "
            "and billing addresses, and your order history. Payment card details are processed by our payment provider "
            "and are never stored on Stride Sports servers.",
            "When you use our website we collect technical information such as your IP address, browser type and the "
            "pages you visit. If you connect a PacerPro watch to your account we store the training data you choose "
            "to sync, such as distance, pace and heart rate.",
        ]),
        ("How We Use Your Information", [
            "We use your information to process and deliver orders, handle returns and warranty claims, provide "
            "customer support, and prevent fraud. With your consent we also use it to send marketing emails and "
            "personalised product recommendations. You can unsubscribe from marketing emails at any time using the "
            "link at the bottom of every email.",
        ]),
        ("Sharing Your Information", [
            "We never sell your personal information. We share it only with service providers who help us run the "
            "business, such as carriers, payment processors and our email provider, and only as much as they need to "
            "do their job. We may also share information when required by law.",
        ]),
        ("Cookies", [
            "We use essential cookies to keep you signed in and remember your shopping cart. Analytics and advertising "
            "cookies are only set if you accept them in the cookie banner. You can change your cookie choices at any "
            "time from the Cookie Settings link in the website footer.",
        ]),
        ("Your Rights", [
            "You can ask to see the personal information we hold about you, correct it, or have it deleted. To make a "
            "request, email privacy@stridesports.example or use the Privacy section of your account. We respond to all "
            "requests within 30 days. Deleting your account removes your order history and synced training data, "
            "although we keep invoices for 7 years because tax law requires it.",
        ]),
        ("Data Retention and Security", [
            "We keep account information for as long as your account is active and for 2 years after your last order. "
            "All data is encrypted in transit and at rest, and access is limited to staff who need it for their work.",
        ]),
        ("Children's Privacy", [
            "Our website and Stride Club membership are intended for people aged 16 and over. We do not knowingly "
            "collect personal information from children. If you believe a child has created an account, contact us "
            "and we will delete it.",
        ]),
        ("Changes to This Policy", [
            "We may update this policy when our services or the law change. If we make a significant change we will "
            "notify you by email at least 14 days before it takes effect. The effective date at the bottom of each "
            "page shows when the policy was last updated.",
        ]),
        ("Contact Us", [
            "For any privacy question, email privacy@stridesports.example or write to Stride Sports Privacy Team, "
            "100 Harbor Street, Portland, OR 97201, United States. You also have the right to complain to your local "
            "data protection authority.",
        ]),
    ]),
}

# 15 valid products + 1 deliberately broken row (no name, bad price) to exercise validation.
PRODUCTS = [
    # SKU, Product Name, Brand, Category, Price, Stock, Color, Size, Material, Description
    ("00123", "Trailblaze Running Shoe", "Stride", "Footwear > Running", "89.99", "Yes", "blue", "38-46", "mesh",
     "Lightweight neutral road running shoe with a responsive foam midsole and breathable mesh upper. Ideal for daily training up to half-marathon distance."),
    ("00124", "Trailblaze GTX Waterproof Running Shoe", "Stride", "Footwear > Trail", "129.99", "yes", "black", "38-46", "waterproof membrane",
     "Waterproof version of the Trailblaze with a sealed membrane that keeps feet dry in rain and puddles, plus a grippy lugged outsole."),
    ("00231", "Aerofoot Cloudrunner", "Aerofoot", "Footwear > Running", "119.00", "0", "white", "36-45", "knit",
     "Max-cushion running shoe with a soft, bouncy ride for long runs and recovery days. Knit upper with a sock-like fit."),
    ("00232", "Aerofoot Rainshield Trail Shoe", "Aerofoot", "Footwear > Trail", "94.50", "Yes", "green", "37-46", "water-resistant mesh",
     "Water-resistant trail running shoe for wet and muddy paths. Rock plate protects against sharp stones."),
    ("01001", "Summit Peak Hiking Boot", "Summit Peak", "Footwear > Hiking", "159.99", "no", "brown", "38-47", "leather",
     "Mid-height waterproof leather hiking boot with ankle support for multi-day hikes on rough terrain."),
    ("02010", "DryFit Running T-Shirt", "Stride", "Apparel > Tops", "24.99", "Yes", "red", "XS-XXL", "polyester",
     "Quick-drying short-sleeve running shirt that wicks sweat away from the skin. Reflective logo for visibility."),
    ("02011", "Thermal Long-Sleeve Running Top", "Stride", "Apparel > Tops", "39.99", "Yes", "navy", "XS-XXL", "brushed polyester",
     "Warm brushed-fleece running top for cold winter mornings, with thumb holes and a zipped chest pocket."),
    ("02020", "Pacer 5-inch Running Shorts", "Pacer", "Apparel > Bottoms", "29.99", "Yes", "black", "S-XL", "nylon",
     "Light running shorts with a built-in liner and a back pocket that fits a phone or energy gels."),
    ("02030", "Hydra Packable Rain Jacket", "Hydra", "Apparel > Outerwear", "79.99", "Yes", "yellow", "S-XL", "ripstop nylon",
     "Waterproof, breathable running jacket that packs into its own pocket. Taped seams and an adjustable hood."),
    ("03001", "Hydra Trail Hydration Vest 5L", "Hydra", "Accessories > Hydration", "64.99", "Yes", "grey", "S/M, L/XL", "stretch mesh",
     "Running vest with 5 litres of storage and two 500 ml soft flasks included. Bounce-free fit for ultra and trail races."),
    ("03002", "Hydra Insulated Water Bottle 750ml", "Hydra", "Accessories > Hydration", "19.99", "Yes", "silver", "750 ml", "stainless steel",
     "Double-wall insulated bottle that keeps drinks cold for 24 hours. Leak-proof lid, dishwasher safe."),
    ("03010", "Compression Running Socks (3-pack)", "Pacer", "Accessories > Socks", "17.99", "Yes", "mixed", "S-L", "nylon blend",
     "Graduated compression socks that support calves and reduce fatigue on long runs. Cushioned heel and toe."),
    ("04001", "PacerPro GPS Running Watch", "PacerPro", "Electronics > Watches", "199.00", "Yes", "black", "one size", "polymer",
     "GPS running watch with wrist heart rate, training plans and 14-day battery life. Water resistant to 50 metres."),
    ("04002", "PacerPro Chest Strap Heart Rate Monitor", "PacerPro", "Electronics > Sensors", "49.99", "0", "black", "one size", "textile",
     "Accurate chest strap heart rate monitor with Bluetooth and ANT+. Pairs with PacerPro watches and most training apps."),
    ("05001", "Stride Foam Recovery Roller", "Stride", "Accessories > Recovery", "27.50", "Yes", "orange", "33 cm", "EVA foam",
     "Firm foam roller with a textured surface for post-run massage of calves, quads and IT band."),
    ("06001", "", "Stride", "Accessories > Bags", "abc", "Yes", "black", "20 L", "polyester",
     "Broken row on purpose: missing name and an invalid price. Ingestion should skip it and log why."),
]


def make_pdf(path: Path, title: str, sections: list[tuple[str, list[str]]]) -> int:
    """Lay out HTML with PyMuPDF's Story (handles page breaks), then stamp a footer on each page."""
    html = f"<h1>{STORE}</h1><h2>{title}</h2>"
    for heading, paragraphs in sections:
        html += f"<h3>{heading}</h3>" + "".join(f"<p>{p}</p>" for p in paragraphs)
    css = "* {font-family: sans-serif;} h1 {font-size: 18pt;} h2 {font-size: 15pt;} h3 {font-size: 12pt; margin-top: 12pt;} p {font-size: 11pt; line-height: 1.5;}"

    page_rect = pymupdf.paper_rect("a4")
    content_rect = page_rect + (60, 60, -60, -70)  # margins; leave room for the footer
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    story = pymupdf.Story(html=html, user_css=css)
    more = True
    while more:
        device = writer.begin_page(page_rect)
        more, _ = story.place(content_rect)
        story.draw(device)
        writer.end_page()
    writer.close()

    doc = pymupdf.open("pdf", buf.getvalue())
    for i, page in enumerate(doc, start=1):
        # Same footer line on every page -> the loader should detect and drop it.
        page.insert_text((60, page_rect.height - 40), FOOTER, fontsize=8, color=(0.4, 0.4, 0.4))
        page.insert_text((page_rect.width - 110, page_rect.height - 40), f"Page {i} of {doc.page_count}", fontsize=8, color=(0.4, 0.4, 0.4))
    doc.save(path)
    return doc.page_count


def make_catalogue(path: Path) -> None:
    columns = ["SKU", "Product Name", "Brand", "Category", "Price", "Stock", "Color", "Size", "Material", "Description"]
    df = pd.DataFrame(PRODUCTS, columns=columns)
    df.to_excel(path, index=False, sheet_name="Products")  # all cells written as text, so "00123" keeps its zeros


if __name__ == "__main__":
    (DATA / "pdfs").mkdir(parents=True, exist_ok=True)
    for filename, (title, sections) in POLICIES.items():
        pages = make_pdf(DATA / "pdfs" / filename, title, sections)
        print(f"data/pdfs/{filename}: {pages} pages")
    make_catalogue(DATA / "catalogue.xlsx")
    print(f"data/catalogue.xlsx: {len(PRODUCTS)} rows (1 intentionally invalid)")
