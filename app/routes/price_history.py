from fastapi import APIRouter, HTTPException
from datetime import datetime
from app.db import supabase
import requests
from bs4 import BeautifulSoup
from fastapi import Path
from fake_useragent import UserAgent
from app.utils.email import send_alert_email
import re

router = APIRouter()

@router.post("/scrape/kelz0r")
def run_kelz0r_scraper():
    # now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # print(f"[🕒 {now}] Running scrape_all_sites()")

    try:
        response = supabase.table("tracked_products").select("*").eq("site_id", 1).eq("active", True).execute()
        products = response.data
        print(f"[🐞] Retrieved {len(products)} products for Kelz0r.")
    except Exception as e:
        print(f"[❌] Error fetching products: {e}")
        return

    for product in products:
        try:
            print(f"[🔍] Scraping Kelz0r product: {product['product_name']}")
            ua = UserAgent()
            headers = {
                "User-Agent": ua.random,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0",
                "Referer": "https://www.google.com/"
            }
            res = requests.get(product["product_url"], headers=headers, timeout=10)
            # print("[🧪] HTML snippet:")
            # print(res.text[:1000])  # Print first 1000 characters of the page
            soup = BeautifulSoup(res.content, "html.parser")

            price_element = soup.find("span", class_="proinfoprice")
            if not price_element:
                raise ValueError("Price element not found")

            inner_span = price_element.find("span")
            if not inner_span:
                raise ValueError("Inner price span not found")

            price_text = inner_span.get_text(strip=True)

            # Normalize and convert
            price_text = (
                price_text.replace("kr", "").replace(".", "").replace(",", ".").strip()
            )
            price = float(price_text)
            
            # Insert into price history
            supabase.table("price_history").insert({
                "product_id": product["id"],
                "price": price,
                "currency": "DKK",
                "checked_at": datetime.now().isoformat()
            }).execute()

            print(f"[✔️] Kelz0r price scraped and stored: {price} DKK")

            # Auto alert logic
            maybe_send_alert(product, price)


        except Exception as e:
            print(f"[❌] Error scraping/storing price for product ID {product['id']}: {e}")

@router.post("/scrape/matraws")
def run_matraws_scraper():
    try:
        response = supabase.table("tracked_products").select("*").eq("site_id", 2).eq("active", True).execute()
        products = response.data
        print(f"[🐞] Retrieved {len(products)} products for Matraws.")
    except Exception as e:
        print(f"[❌] Error fetching Matraws products: {e}")
        return

    for product in products:
        try:
            print(f"[🔍] Scraping Matraws product: {product['product_name']}")
            ua = UserAgent()
            headers = {
                "User-Agent": ua.random,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0",
                "Referer": "https://www.google.com/"
            }

            res = requests.get(product["product_url"], headers=headers, timeout=10)
            res.encoding = 'utf-8'  # enforce correct decoding
            soup = BeautifulSoup(res.content, "html.parser")
            
            price = extract_matraws_price(product["product_url"])

            # Store price
            supabase.table("price_history").insert({
                "product_id": product["id"],
                "price": price,
                "currency": "DKK",
                "checked_at": datetime.now().isoformat()
            }).execute()

            print(f"[✔️] Matraws price scraped and stored: {price} DKK")
            
            # Auto alert logic
            maybe_send_alert(product, price)

            
        except Exception as e:
            print(f"[❌] Error scraping/storing Matraws price for product ID {product['id']}: {e}")

def extract_matraws_price(url: str) -> float:
    ua = UserAgent()
    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
    }

    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    strong_tag = soup.find("strong", class_="price__current")
    if not strong_tag:
        raise ValueError("Price element not found")

    sup_tag = strong_tag.find("sup")
    sup_text = sup_tag.get_text(strip=True) if sup_tag else "00"

    # Remove sup tag so it doesn’t appear in main text
    if sup_tag:
        sup_tag.extract()

    main_text = strong_tag.get_text(strip=True)

    # Combine using a dot (.)
    full_price = f"{main_text}.{sup_text}"

    # Remove thousands separator (.)
    full_price = full_price.replace(".", "", full_price.count(".") - 1)
    
    full_price = full_price.replace("kr", "").replace("\xa0", "").strip()
    
    return float(full_price)

@router.post("/scrape/pokemons")
def run_pokemons_scraper():
    try:
        response = supabase.table("tracked_products").select("*").eq("site_id", 3).eq("active", True).execute()
        products = response.data
        print(f"[🐞] Retrieved {len(products)} products for Pokemons.")
    except Exception as e:
        print(f"[❌] Error fetching Pokemons products: {e}")
        return

    for product in products:
        try:
            print(f"[🔍] Scraping Pokemons product: {product['product_name']}")
            price = extract_pokemons_price(product["product_url"])

            # Store price
            supabase.table("price_history").insert({
                "product_id": product["id"],
                "price": price,
                "currency": "DKK",
                "checked_at": datetime.now().isoformat()
            }).execute()

            print(f"[✔️] Pokemons price scraped and stored: {price} DKK")
            
            # Auto alert logic
            maybe_send_alert(product, price)

            
        except Exception as e:
            print(f"[❌] Error scraping/storing Pokemons price for product ID {product['id']}: {e}")


def extract_pokemons_price(url: str) -> float:
    ua = UserAgent()
    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
    }

    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    # ✅ Look for the meta tag with the price
    meta_tag = soup.find("meta", {"property": "product:price:amount"})
    if not meta_tag or not meta_tag.get("content"):
        raise ValueError("Price meta tag not found")

    price_text = meta_tag["content"]
    #print(f"[🧪] Extracted price from meta: {price_text}")
    return float(price_text)

@router.post("/scrape/qubimon")
def run_qubimon_scraper():
    try:
        response = supabase.table("tracked_products").select("*").eq("site_id", 4).eq("active", True).execute()
        products = response.data
        print(f"[🐞] Retrieved {len(products)} products for Qubimon.")
    except Exception as e:
        print(f"[❌] Error fetching Qubimon products: {e}")
        return

    for product in products:
        try:
            print(f"[🔍] Scraping Qubimon product: {product['product_name']}")
            price = extract_qubimon_price(product["product_url"])

            supabase.table("price_history").insert({
                "product_id": product["id"],
                "price": price,
                "currency": "DKK",
                "checked_at": datetime.now().isoformat()
            }).execute()

            print(f"[✔️] Qubimon price scraped and stored: {price} DKK")

            # Auto alert logic
            maybe_send_alert(product, price)


        except Exception as e:
            print(f"[❌] Error scraping/storing Qubimon price for product ID {product['id']}: {e}")

def extract_qubimon_price(url: str) -> float:
    ua = UserAgent()
    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
    }

    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    meta_tag = soup.find("meta", property="og:price:amount")
    if not meta_tag or not meta_tag.get("content"):
        raise ValueError("Price meta tag not found")

    price_raw = meta_tag["content"]
    cleaned = price_raw.replace(".", "").replace(",", ".").strip()

    return float(cleaned)

@router.post("/scrape/rogerz")
def run_rogerz_scraper():
    try:
        response = supabase.table("tracked_products").select("*").eq("site_id", 5).eq("active", True).execute()
        products = response.data
        print(f"[🐞] Retrieved {len(products)} products for Rogerz.")
    except Exception as e:
        print(f"[❌] Error fetching Rogerz products: {e}")
        return

    for product in products:
        try:
            print(f"[🔍] Scraping Rogerz product: {product['product_name']}")
            price = extract_rogerz_price(product["product_url"])

            supabase.table("price_history").insert({
                "product_id": product["id"],
                "price": price,
                "currency": "DKK",
                "checked_at": datetime.now().isoformat()
            }).execute()

            print(f"[✔️] Rogerz price scraped and stored: {price} DKK")

            # Auto alert logic
            maybe_send_alert(product, price)

        except Exception as e:
            print(f"[❌] Error scraping/storing Rogerz price for product ID {product['id']}: {e}")

def extract_rogerz_price(url: str) -> float:
    ua = UserAgent()
    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
    }

    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    span = soup.find("span", class_="money", attrs={"data-price": True})
    if not span:
        raise ValueError("Price element not found")

    price_text = span.get_text(strip=True)
    cleaned = price_text.replace("kr", "").replace(".", "").replace(",", ".").strip()
    return float(cleaned)


@router.get("/product/{product_id}")
def get_price_history(product_id: int = Path(..., description="Tracked product ID")):
    result = supabase.table("price_history") \
        .select("*") \
        .eq("product_id", product_id) \
        .order("checked_at", desc=False) \
        .execute()

    return result.data
    
def maybe_send_alert(product, price):
    if product.get("auto_alert") and product.get("alert_price") is not None and product.get("alert_direction"):
        alert_price = float(product["alert_price"])
        direction = product["alert_direction"]
        last_alerted = product.get("last_alerted_price")

        should_alert = (
            (direction == "below" and price <= alert_price and (last_alerted is None or last_alerted > alert_price))
            or
            (direction == "above" and price >= alert_price and (last_alerted is None or last_alerted < alert_price))
        )

        if should_alert:
            profile = supabase.table("profiles").select("user_id").eq("id", product["profile_id"]).execute()
            if profile.data:
                user_id = profile.data[0]["user_id"]
                user = supabase.table("users").select("email").eq("id", user_id).execute()
                if user.data:
                    email = user.data[0]["email"]
                    send_alert_email(email, product["product_name"], product["product_url"], price)
                    print(f"[📧] Alert email sent to {email} (price {price} vs alert {alert_price})")
                    supabase.table("tracked_products").update({"last_alerted_price": price}).eq("id", product["id"]).execute()
    