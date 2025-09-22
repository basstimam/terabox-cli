import requests
from typing import Dict, Any, Optional, List
import logging
import re
import base64
import urllib.parse
import random
import json
from urllib.parse import quote

# Daftar base URL workers.dev yang lebih lengkap
BASE_URLS = [
    'plain-grass-58b2.comprehensiveaquamarine',
    'bold-hall-f23e.7rochelle',
    'winter-thunder-0360.belitawhite',
    'fragrant-term-0df9.elviraeducational',
    'purple-glitter-924b.miguelalocal'
]

# Beberapa alternatif workers jika yang utama gagal
# Prioritas endpoint berdasarkan memory: terabox.hnn.workers.dev prioritas utama
# Skip endpoint yang diketahui tidak berfungsi: terabox.app.workers.dev dan terabox.cf.workers.dev
WORKERS_ENDPOINTS = [
    "https://terabox.hnn.workers.dev",  # Primary endpoint dengan prioritas tinggi
]

# Tambahkan endpoint alternatif dari BASE_URLS
for base_url in BASE_URLS:
    WORKERS_ENDPOINTS.append(f"https://{base_url}.workers.dev")

# Default ke endpoint pertama
WORKERS_BASE_URL = WORKERS_ENDPOINTS[0]

logger = logging.getLogger(__name__)


def extract_shorturl(url: str) -> Optional[str]:
    """
    Ekstrak shorturl dari URL TeraBox lengkap.

    Args:
        url (str): URL TeraBox lengkap

    Returns:
        Optional[str]: Shorturl jika ditemukan, None jika tidak
    """
    # Pattern untuk mencocokkan shorturl
    patterns = [
        r'terabox\.com/s/([^/?&]+)',
        r'1024tera\.com/s/([^/?&]+)',
        r'4funbox\.com/s/([^/?&]+)',
        r'mirrobox\.com/s/([^/?&]+)',
        r'teraboxapp\.com/s/([^/?&]+)',
        r'surl=([^&]+)',
        r'/s/([^/?&]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # Jika URL sudah berupa shorturl
    if re.match(r'^[a-zA-Z0-9_-]{10,25}$', url):
        return url
        
    return None


def set_base_url(index: int = 0) -> None:
    """
    Set base URL untuk workers API.

    Args:
        index (int): Indeks endpoint yang akan digunakan
    """
    global WORKERS_BASE_URL
    if 0 <= index < len(WORKERS_ENDPOINTS):
        WORKERS_BASE_URL = WORKERS_ENDPOINTS[index]
        logger.info(f"Menggunakan endpoint: {WORKERS_BASE_URL}")


def is_proxy_url(url: str) -> bool:
    """
    Cek apakah URL adalah URL proxy workers.

    Args:
        url (str): URL yang akan dicek

    Returns:
        bool: True jika URL adalah proxy, False jika tidak
    """
    for endpoint in WORKERS_ENDPOINTS:
        if url.startswith(endpoint) and "?url=" in url:
            return True
    
    # Cek pola umum URL proxy workers
    proxy_patterns = [
        r'https?://[^/]+\.workers\.dev/\?url=',
        r'https?://[^/]+\.workers\.dev/proxy\?url='
    ]
    
    for pattern in proxy_patterns:
        if re.search(pattern, url):
            return True
    
    return False


def decode_proxy_url(url: str) -> str:
    """
    Decode URL proxy workers ke URL asli.

    Args:
        url (str): URL proxy

    Returns:
        str: URL asli
    """
    try:
        # Ekstrak bagian base64
        encoded_part = url.split("?url=")[1]
        # Decode base64
        decoded_bytes = base64.urlsafe_b64decode(encoded_part + "=" * (4 - len(encoded_part) % 4))
        # Decode URL encoding
        real_url = urllib.parse.unquote(decoded_bytes.decode('utf-8'))
        logger.info(f"URL proxy terdeteksi, URL asli: {real_url[:100]}...")
        return real_url
    except Exception as e:
        logger.error(f"Gagal decode URL proxy: {e}")
        return url


def wrap_url(original_url: str) -> str:
    """
    Bungkus url asli setelah di-quote, lalu base64.

    Args:
        original_url (str): URL asli yang akan dibungkus

    Returns:
        str: URL proxy hasil pembungkusan
    """
    selected_base = random.choice(BASE_URLS)
    quoted_url = quote(original_url, safe='')
    b64_encoded = base64.urlsafe_b64encode(quoted_url.encode()).decode()
    return f'https://{selected_base}.workers.dev/?url={b64_encoded}'


def get_info(shorturl: str, cookies: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """
    Mendapatkan informasi file/folder dari shorturl TeraBox via workers.dev.
    Menggunakan endpoint /api/get-info-new sebagai prioritas utama dengan fallback ke /api/get-info.

    Args:
        shorturl (str): Kode shorturl dari link TeraBox (contoh: '1DcGWQPuMVDgkXrFhP7AlcQ').
        cookies (Optional[Dict[str, str]]): Cookies opsional untuk request.

    Returns:
        Optional[Dict[str, Any]]: Hasil JSON dari API jika sukses, None jika gagal.
    """
    # Ekstrak shorturl jika yang diberikan adalah URL lengkap
    extracted = extract_shorturl(shorturl)
    if extracted:
        shorturl = extracted
    
    params = {"shorturl": shorturl, "pwd": ""}
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.112 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "sec-ch-ua": '"Not(A:Brand";v="24", "Chromium";v="122"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Priority": "u=1, i"
    }
    
    # Endpoint API yang akan dicoba berdasarkan prioritas
    api_endpoints = ["/api/get-info-new", "/api/get-info"]
    
    # Coba semua endpoint dengan fallback mechanism
    for i, base_url in enumerate(WORKERS_ENDPOINTS):
        # Update headers untuk endpoint saat ini
        headers["Referer"] = f"{base_url}/"
        headers["Origin"] = base_url
        
        # Coba endpoint utama terlebih dahulu, kemudian fallback
        for api_endpoint in api_endpoints:
            try:
                current_url = f"{base_url}{api_endpoint}"
                logger.info(f"Mencoba endpoint: {current_url}")
                
                resp = requests.get(current_url, params=params, headers=headers, cookies=cookies, timeout=20)
                resp.raise_for_status()
                
                # Handle potential JSON parsing issues by ensuring proper decoding
                try:
                    # Let requests handle decompression automatically
                    data = resp.json()
                except ValueError as e:
                    logger.warning(f"Endpoint {current_url} tidak mengembalikan JSON valid: {e}")
                    logger.warning(f"Response content type: {resp.headers.get('content-type', 'unknown')}")
                    logger.warning(f"Response status: {resp.status_code}")
                    logger.warning(f"Response encoding: {resp.encoding}")
                    logger.warning(f"Response headers: {dict(resp.headers)}")
                    logger.warning(f"Response raw content preview: {repr(resp.content[:100])}")
                    
                    # Try to get text and parse manually
                    try:
                        text_content = resp.text
                        if text_content.strip():
                            data = json.loads(text_content)
                            logger.info(f"Successfully parsed JSON from text content")
                        else:
                            logger.warning("Empty response text")
                            continue
                    except Exception as e2:
                        logger.warning(f"Failed to parse JSON from text: {e2}")
                        continue
                
                if data.get("ok"):
                    logger.info(f"Berhasil mendapatkan info dari {current_url}")
                    # Jika berhasil, set base URL ke endpoint yang berhasil
                    set_base_url(i)
                    return data
                    
                logger.warning(f"Endpoint {current_url} return tidak ok: {data}")
                
            except Exception as e:
                logger.warning(f"Exception pada endpoint {current_url}: {e}")
    
    logger.error(f"Semua endpoint gagal untuk shorturl: {shorturl}")
    return None


def get_download_link(params: Dict[str, Any], cookies: Optional[Dict[str, str]] = None, shorturl: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Mendapatkan direct download link dari workers.dev.
    Menggunakan endpoint /api/get-downloadp.

    Args:
        params (Dict[str, Any]): Dict berisi shareid, uk, sign, timestamp, fs_id.
        cookies (Optional[Dict[str, str]]): Cookies opsional untuk request.
        shorturl (Optional[str]): Shorturl untuk refresh token jika diperlukan.

    Returns:
        Optional[Dict[str, Any]]: Hasil JSON dari API jika sukses, None jika gagal.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.112 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Accept-Encoding": "gzip, deflate",
        "sec-ch-ua": '"Not(A:Brand";v="24", "Chromium";v="122"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Priority": "u=1, i"
    }
    
    # Coba semua endpoint jika gagal
    for i, base_url in enumerate(WORKERS_ENDPOINTS):
        try:
            current_url = f"{base_url}/api/get-downloadp"
            headers["Referer"] = f"{base_url}/"
            headers["Origin"] = base_url
            
            resp = requests.post(current_url, json=params, headers=headers, cookies=cookies, timeout=20)
            resp.raise_for_status()
            
            # Handle potential JSON parsing issues by ensuring proper decoding
            try:
                # Let requests handle decompression automatically
                data = resp.json()
            except ValueError as e:
                logger.warning(f"Endpoint {current_url} tidak mengembalikan JSON valid: {e}")
                logger.warning(f"Response content type: {resp.headers.get('content-type', 'unknown')}")
                logger.warning(f"Response status: {resp.status_code}")
                logger.warning(f"Response encoding: {resp.encoding}")
                logger.warning(f"Response headers: {dict(resp.headers)}")
                logger.warning(f"Response raw content preview: {repr(resp.content[:100])}")
                
                # Try to get text and parse manually
                try:
                    text_content = resp.text
                    if text_content.strip():
                        data = json.loads(text_content)
                        logger.info(f"Successfully parsed JSON from text content")
                    else:
                        logger.warning("Empty response text")
                        continue
                except Exception as e2:
                    logger.warning(f"Failed to parse JSON from text: {e2}")
                    continue
            
            if data.get("ok"):
                # Jika berhasil, set base URL ke endpoint yang berhasil
                set_base_url(i)
                
                # Log download link yang berhasil didapatkan
                download_link = data.get('downloadLink', '')
                if download_link:
                    logger.info(f"Berhasil mendapatkan download link: {download_link[:100]}...")
                    
                    # Cek apakah ini URL proxy
                    if is_proxy_url(download_link):
                        logger.info("URL download adalah URL proxy workers")
                        # Decode URL proxy untuk mendapatkan URL asli
                        real_url = decode_proxy_url(download_link)
                        # Update data dengan URL asli untuk logging
                        data['originalLink'] = real_url
                
                return data
            else:
                # Handle specific errors
                error_msg = data.get('message', 'Unknown error')
                if 'KVTOKENS' in error_msg:
                    logger.warning(f"Endpoint {base_url} mengalami masalah konfigurasi (KVTOKENS): {error_msg}")
                elif 'expired' in error_msg.lower() or 'invalid' in error_msg.lower():
                    logger.warning(f"Endpoint {base_url} mengatakan token expired/invalid: {error_msg}")
                    # Try to refresh token if shorturl is provided
                    if shorturl and i == 0:  # Only retry on first endpoint
                        logger.info(f"Mencoba refresh token untuk {base_url}...")
                        fresh_info = get_info(shorturl)
                        if fresh_info and fresh_info.get('ok'):
                            # Update params with fresh token data
                            params.update({
                                'shareid': int(fresh_info['shareid']),
                                'uk': int(fresh_info['uk']),
                                'sign': str(fresh_info['sign']),
                                'timestamp': int(fresh_info['timestamp'])
                            })
                            logger.info(f"Token berhasil di-refresh, mencoba download lagi...")
                            # Retry the request with fresh params
                            try:
                                resp = requests.post(current_url, json=params, headers=headers, cookies=cookies, timeout=20)
                                resp.raise_for_status()
                                data = resp.json()
                                if data.get("ok"):
                                    logger.info(f"Berhasil dengan token yang di-refresh!")
                                    download_link = data.get('downloadLink', '')
                                    if download_link:
                                        logger.info(f"Berhasil mendapatkan download link: {download_link[:100]}...")
                                        if is_proxy_url(download_link):
                                            data['originalLink'] = decode_proxy_url(download_link)
                                    return data
                            except Exception as retry_e:
                                logger.warning(f"Retry dengan token fresh juga gagal: {retry_e}")
                else:
                    logger.warning(f"Endpoint {base_url} gagal: {data}")
            
        except Exception as e:
            logger.warning(f"Exception pada endpoint {base_url}: {e}")
    
    logger.error(f"Semua endpoint gagal untuk params: {params}")
    return None 