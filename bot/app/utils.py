def parse_tags(raw: str) -> list[str]:
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def format_profile(profile: dict) -> str:
    tags = ", ".join(profile.get("tags", [])) if profile.get("tags") else "—"
    username = f"@{profile['username']}" if profile.get("username") else "—"

    return (
        f"🎨 <b>{profile.get('artist_name', '—')}</b>\n"
        f"Display name: {profile.get('display_name', '—')}\n"
        f"Username: {username}\n"
        f"Bio: {profile.get('short_bio') or '—'}\n"
        f"Portfolio: {profile.get('portfolio_link') or '—'}\n"
        f"Contact: {profile.get('contact_info') or '—'}\n"
        f"Commissions: {profile.get('commission_status') or '—'}\n"
        f"Tags: {tags}\n"
        f"Price range: {profile.get('price_range') or '—'}\n"
        f"Created: {profile.get('created_at')}\n"
        f"Updated: {profile.get('updated_at')}"
    )