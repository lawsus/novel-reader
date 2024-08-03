from flask import Flask, render_template, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import re
import sqlite3
from urllib.parse import urljoin
from config import CONFIG

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('chapters.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chapters
                 (url TEXT PRIMARY KEY, content TEXT, prev_url TEXT, next_url TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS last_url
                 (id INTEGER PRIMARY KEY, url TEXT)''')
    conn.commit()
    conn.close()

init_db()

def get_chapter_from_db(url):
    conn = sqlite3.connect('chapters.db')
    c = conn.cursor()
    c.execute("SELECT content, prev_url, next_url FROM chapters WHERE url = ?", (url,))
    result = c.fetchone()
    conn.close()
    return result

def save_chapter_to_db(url, content, prev_url, next_url):
    conn = sqlite3.connect('chapters.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO chapters (url, content, prev_url, next_url) VALUES (?, ?, ?, ?)",
              (url, content, prev_url, next_url))
    conn.commit()
    conn.close()
    print(f"Chapter saved to database: {url}")

def extract_reader_view(url):
    print(f"extract_reader_view({url})")
    db_result = get_chapter_from_db(url)
    if db_result:
        content, prev_url, next_url = db_result
        return content, prev_url, next_url

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, CONFIG['content_class']))
        )
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        content = soup.find(class_=CONFIG['content_class'])

        next_chapter_link = soup.find('a', rel='next', class_=CONFIG['next_chapter_class'])
        next_chapter_url = urljoin(CONFIG['base_url'], next_chapter_link['href']) if next_chapter_link else None

        prev_chapter_link = soup.find('a', rel='prev', class_=CONFIG['prev_chapter_class'])
        prev_chapter_url = urljoin(CONFIG['base_url'], prev_chapter_link['href']) if prev_chapter_link else None

        if content:
            formatted_content = str(content)
            formatted_content = re.sub(r'<em>(.*?)</em>', r'\1', formatted_content)
            formatted_content = re.sub(r'<br\s*/?>', '\n', formatted_content)
            formatted_content = re.sub(r'<p.*?>(.*?)</p>', r'\1\n\n', formatted_content, flags=re.DOTALL)
            formatted_content = re.sub(r'<[^>]+>', '', formatted_content)
            formatted_content = '\n'.join(line.strip() for line in formatted_content.split('\n'))
            formatted_content = re.sub(r'\n{3,}', '\n\n', formatted_content)
            
            save_chapter_to_db(url, formatted_content.strip(), prev_chapter_url, next_chapter_url)
            
            return formatted_content.strip(), prev_chapter_url, next_chapter_url
        else:
            return "Could not find the main content.", None, None
    finally:
        driver.quit()

def get_last_url():
    conn = sqlite3.connect('chapters.db')
    c = conn.cursor()
    c.execute("SELECT url FROM last_url WHERE id = 1")
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def save_last_url(url):
    conn = sqlite3.connect('chapters.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO last_url (id, url) VALUES (1, ?)", (url,))
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    content = ""
    prev_chapter_url = None
    next_chapter_url = None
    last_url = get_last_url()
    show_last_url = True

    if request.method == 'POST':
        if 'home' in request.form:
            pass
        else:
            url = request.form.get('url') or last_url
            if url:
                save_last_url(url)
                content, prev_chapter_url, next_chapter_url = extract_reader_view(url)
                show_last_url = False

    return render_template('index.html', 
                           content=content, 
                           prev_chapter_url=prev_chapter_url, 
                           next_chapter_url=next_chapter_url, 
                           base_url=CONFIG['base_url'],
                           last_url=last_url,
                           show_last_url=show_last_url)

if __name__ == '__main__':
    app.run(debug=True)