from flask import Flask, request, jsonify
# from flask_cors import CORS
from freewebnovel import FreeWebNovelAPI

app = Flask(__name__)
# CORS(app, resources={r"/*": {"origins": "*"}})

novel_api = FreeWebNovelAPI()  # For novel operations

@app.route('/')
def home():
    return 'Hello, World!'

# Original chapter text extraction endpoint
@app.route('/extract_text', methods=['POST'])
def extract_text():
    """Extract text content from a specific chapter"""
    data = request.json
    if not data or 'novel' not in data or 'num' not in data:
        return jsonify({"error": "Missing 'novel' or 'num' parameter"}), 400

    novel = data['novel']
    num = data['num']
    
    try:
        results = novel_api.extract_chapter(novel, num)
        if not results: jsonify({"error": f"Chapter extract failed, text none"}), 500
        return jsonify({"text": results}), 200
        
    except Exception as e:
        return jsonify({"error": f"Chapter extract  failed: {str(e)}"}), 500

# Search novels
@app.route('/search', methods=['POST'])
def search_novels():
    """Search for novels by query string"""
    data = request.json
    if not data or 'query' not in data:
        return jsonify({"error": "Missing 'query' parameter"}), 400
    
    query = data['query']
    
    try:
        results = novel_api.search(query)
        return jsonify({
            "query": query,
            "results": results,
            "count": len(results)
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Search failed: {str(e)}"}), 500

# Get novel categories
@app.route('/categories', methods=['GET'])
def get_categories():
    """Get list of all available novel categories"""
    try:
        categories = novel_api.get_categories()
        return jsonify({
            "categories": categories,
            "count": len(categories)
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to get categories: {str(e)}"}), 500

# Browse novels by category
@app.route('/browse', methods=['POST'])
def browse_category():
    """Browse novels by category/genre"""
    data = request.json
    if not data or 'genre' not in data:
        return jsonify({"error": "Missing 'genre' parameter"}), 400
    
    genre = data['genre']
    page = data.get('page', 1)
    
    try:
        novels = novel_api.browse_category(genre, page)
        return jsonify({
            "genre": genre,
            "page": page,
            "novels": novels,
            "count": len(novels)
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Browse failed: {str(e)}"}), 500

# Get detailed novel information
@app.route('/novel_info', methods=['POST'])
def get_novel_info():
    """Get detailed information about a specific novel"""
    data = request.json
    if not data or 'path' not in data:
        return jsonify({"error": "Missing 'path' parameter"}), 400
    
    novel_path = data['path']
    
    try:
        novel_info = novel_api.get_novel_info(novel_path)
        return jsonify({
            "novel": novel_info.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to get novel info: {str(e)}"}), 500

# Get novel info by novel slug (alternative endpoint)
@app.route('/novel/<novel_slug>', methods=['GET'])
def get_novel_by_slug(novel_slug):
    """Get detailed information about a novel using URL parameter"""
    try:
        novel_path = f"novel/{novel_slug}"
        novel_info = novel_api.get_novel_info(novel_path)
        return jsonify({
            "novel": novel_info.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to get novel info: {str(e)}"}), 500

# Combined search and info endpoint
@app.route('/search_detailed', methods=['POST'])
def search_detailed():
    """Search for novels and get detailed info for the first result"""
    data = request.json
    if not data or 'query' not in data:
        return jsonify({"error": "Missing 'query' parameter"}), 400
    
    query = data['query']
    get_details = data.get('details', False)
    
    try:
        # Search for novels
        search_results = novel_api.search(query)
        
        response = {
            "query": query,
            "search_results": search_results,
            "count": len(search_results)
        }
        
        # If details requested and we have results, get info for first result
        if get_details and search_results:
            first_result = search_results[0]
            if first_result.get('path'):
                try:
                    detailed_info = novel_api.get_novel_info(first_result['path'])
                    response['detailed_info'] = detailed_info.to_dict()
                except Exception as detail_error:
                    response['detail_error'] = str(detail_error)
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({"error": f"Search failed: {str(e)}"}), 500

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "FreeWebNovel API",
        "endpoints": [
            "/extract_text - POST - Extract chapter text",
            "/search - POST - Search novels",
            "/categories - GET - List categories",
            "/browse - POST - Browse by category",
            "/novel_info - POST - Get novel details",
            "/novel/<slug> - GET - Get novel by slug",
            "/search_detailed - POST - Search with optional details",
            "/health - GET - Health check"
        ]
    }), 200


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)