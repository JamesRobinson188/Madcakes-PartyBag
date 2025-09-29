import os
from flask import Blueprint, render_template, abort, session

bp = Blueprint("madcakes", __name__)

CATEGORIES = {
    "wedding-cakes": "Wedding Cakes",
    "cupcakes": "Cupcakes",
    "novelty-cakes": "Novelty Cakes",
    "birthday-cakes": "Birthday Cakes",
    "celebration-cakes": "Celebrations Cakes",
    "baby-shower-cakes": "Baby Shower Cakes",
    "corporate-cakes": "Corporate Cakes",
    "adult-novelty-cakes": "Adult Novelty Cakes",
    "customer-creations": "Customer Creations",
}

DESCRIPTIONS = {
    "wedding-cakes": "Elegant designs for your big day.",
    "cupcakes": "Bite-sized joy, perfect for any event.",
    "novelty-cakes": "Playful, creative centrepieces.",
    "birthday-cakes": "Make a wish with style.",
    "celebration-cakes": "Mark every milestone sweetly.",
    "baby-shower-cakes": "Adorable bakes to welcome baby.",
    "corporate-cakes": "On-brand treats for your team.",
    "adult-novelty-cakes": "Cheeky bakes for grown-ups.",
    "customer-creations": "Your ideas, baked to life.",
}

ADULT_SLUGS = {"adult-novelty-cakes"}

@bp.get("/")
def index():
    return render_template("Madcakes/index.html", categories=CATEGORIES)

@bp.get("/<slug>")
def show_category(slug):
    title = CATEGORIES.get(slug)
    if not title: abort(404)
    folder = os.path.join(current_app.root_path, "static", "Madcakes", "imgs", "gallery", slug)
    if not os.path.isdir(folder): abort(404)
    files = sorted([f for f in os.listdir(folder) if f.lower().endswith((".jpg",".jpeg",".png",".webp"))])
    images = [f"/static/Madcakes/imgs/gallery/{slug}/{f}" for f in files]
    if not images: abort(404)
    show_age_gate = (slug in ADULT_SLUGS) and not session.get("adult_verified", False)
    return render_template("Madcakes/gallery.html", title=title, images=images, categories=CATEGORIES, show_age_gate=show_age_gate)


@bp.get("/all-cakes")
def all_cakes():
    previews = {}
    PREVIEW_COUNT = 8

    for slug in CATEGORIES:
        folder = os.path.join(current_app.root_path, "static", "Madcakes", "imgs", "gallery", slug)
        if not os.path.isdir(folder):
            continue
        files = sorted([f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))])
        images = [f"/static/Madcakes/imgs/gallery/{slug}/{f}" for f in files[:PREVIEW_COUNT]]
        if images:
            previews[slug] = images

    return render_template(
        "Madcakes/all-cakes.html",
        categories=CATEGORIES,
        previews=previews,
        descriptions=DESCRIPTIONS,
        adult_verified=session.get("adult_verified", False),
        adult_slugs=ADULT_SLUGS,  # <-- add this
    )

