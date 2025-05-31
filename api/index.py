from flask import Flask, request, jsonify
import cloudscraper
import bs4
# from flask_cors import CORS

app = Flask(__name__)
# CORS(app, resources={r"/convert": {"origins": "*"}})
scraper = cloudscraper.create_scraper()  # Cloudflare bypass

@app.route('/')
def home():
    return 'Hello, World!'

@app.route('/extract_text', methods=['POST'])
def extract_text():
    data = request.json
    if not data or 'novel' not in data or 'num' not in data:
        return jsonify({"error": "Missing 'novel' or 'num' parameter"}), 400

    novel = data['novel']
    num = data['num']

    url = f"https://freewebnovel.com/novel/{novel}/chapter-{num}"
    response = scraper.get(url)

    if response.status_code == 200:
        soup = bs4.BeautifulSoup(response.text, "html.parser")
        paragraphs = soup.find_all('p')
        text = "\n".join(p.text.strip() for p in paragraphs)
        return jsonify({"text": text}), 200
    else:
        return jsonify({"error": f"Failed with status code: {response.status_code}"}), response.status_code

if __name__ == '__main__':
    app.run(debug=True)
