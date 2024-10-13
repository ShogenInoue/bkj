from flask import Flask, render_template_string, request, Response
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote, unquote
import re

app = Flask(__name__)

BASE_URL = 'https://www.google.com'  # Replace with the base URL of the site you are proxying


def modify_inline_urls(html, base_url):
    """Modify URLs in inline styles such as background-image."""
    html = re.sub(r'url\((?!["\']?(?:data|http|https):)["\']?([^)"\']+)["\']?\)',
                  lambda match: f"url(/proxy?url={quote(urljoin(base_url, match.group(1)))})",
                  html)
    return html


def inject_proxy_script(soup):
    """Inject JavaScript to handle dynamic content loading."""
    script = """
    <script type="text/javascript">
    document.addEventListener("DOMContentLoaded", function() {
        var elements = document.querySelectorAll('[src], [href]');
        elements.forEach(function(element) {
            var attr = element.hasAttribute('src') ? 'src' : 'href';
            var url = element.getAttribute(attr);
            if (url && !url.startsWith('http') && !url.startsWith('/proxy?')) {
                element.setAttribute(attr, '/proxy?url=' + encodeURIComponent(window.location.origin + '/' + url));
            }
        });

        // Fix viewport scaling issue
        if (document.querySelector('meta[name=viewport]') === null) {
            var meta = document.createElement('meta');
            meta.name = "viewport";
            meta.content = "width=device-width, initial-scale=1";
            document.getElementsByTagName('head')[0].appendChild(meta);
        }
    });
    </script>
    """
    soup.body.append(BeautifulSoup(script, 'html.parser'))
    return soup


def fetch_and_modify_html(url):
    try:
        response = requests.get(url, allow_redirects=True)
        response.raise_for_status()
        final_url = response.url
        html = response.text

        # Modify inline URLs before parsing the HTML
        html = modify_inline_urls(html, final_url)

        # Parse HTML and update links, images, scripts, and CSS URLs
        soup = BeautifulSoup(html, 'html.parser')

        # Update all links
        for tag in soup.find_all(['a', 'link'], href=True):
            href = tag['href']
            if href.startswith(('http:', 'https:')):  # Absolute URL
                if BASE_URL not in href:
                    tag['href'] = f"/proxy?url={quote(href)}"
            else:  # Relative URL
                absolute_url = urljoin(final_url, href)
                tag['href'] = f"/proxy?url={quote(absolute_url)}"

        # Update images
        for img in soup.find_all('img', src=True):
            src = img['src']
            if src.startswith(('http:', 'https:')):  # Absolute URL
                if BASE_URL not in src:
                    img['src'] = f"/proxy?url={quote(src)}"
            else:  # Relative URL
                absolute_src = urljoin(final_url, src)
                img['src'] = f"/proxy?url={quote(absolute_src)}"

        # Update script sources
        for script in soup.find_all('script', src=True):
            src = script['src']
            if src.startswith(('http:', 'https:')):  # Absolute URL
                if BASE_URL not in src:
                    script['src'] = f"/proxy?url={quote(src)}"
            else:  # Relative URL
                absolute_src = urljoin(final_url, src)
                script['src'] = f"/proxy?url={quote(absolute_src)}"

        # Update CSS links
        for css in soup.find_all('link', rel='stylesheet', href=True):
            href = css['href']
            if href.startswith(('http:', 'https:')):  # Absolute URL
                if BASE_URL not in href:
                    css['href'] = f"/proxy?url={quote(href)}"
            else:  # Relative URL
                absolute_href = urljoin(final_url, href)
                css['href'] = f"/proxy?url={quote(absolute_href)}"

        # Inject proxy script to handle dynamic content
        soup = inject_proxy_script(soup)

        return str(soup)
    except requests.RequestException as e:
        return f"Error fetching content: {e}"


@app.route('/')
def index():
    html_content = fetch_and_modify_html(BASE_URL)
    return render_template_string(html_content)


@app.route('/proxy')
def proxy():
    target_url = request.args.get('url')
    if target_url:
        target_url = unquote(target_url)  # Decode URL
        try:
            response = requests.get(target_url, allow_redirects=True)
            response.raise_for_status()
            content_type = response.headers.get('Content-Type')

            # Ensure proper Content-Type for CSS files
            if 'text/css' in content_type:
                return Response(response.content, content_type='text/css')

            if 'text/html' in content_type:
                modified_html = fetch_and_modify_html(target_url)
                return Response(modified_html, content_type=content_type)
            return Response(response.content, content_type=content_type)
        except requests.RequestException as e:
            return f"Error fetching content: {e}", 404
    return "No URL provided."


@app.route('/<path:subpath>')
def catch_all(subpath):
    full_url = f"{BASE_URL}/{subpath}"
    if request.query_string:
        full_url += f"?{request.query_string.decode('utf-8')}"
    return proxy_request(full_url)


def proxy_request(target_url):
    try:
        response = requests.get(target_url, allow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type')

        # Handle CSS content type
        if 'text/css' in content_type:
            return Response(response.content, content_type='text/css')

        if 'text/html' in content_type:
            modified_html = fetch_and_modify_html(target_url)
            return Response(modified_html, content_type=content_type)
        else:
            return Response(response.content, content_type=content_type)
    except requests.RequestException as e:
        return f"Error fetching content: {e}", 404


if __name__ == '__main__':
    # Enable SSL with the generated certificates
    app.run(host='0.0.0.0', port=8080, ssl_context=(r"C:\Users\Shoge\Downloads\http_ununun-ignorelist.com.crt", r"C:\Users\Shoge\Downloads\http_ununun-ignorelist.com-privateKey.key"), debug=True)
