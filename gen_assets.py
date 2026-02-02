import requests
import os
import time

API_BASE = "https://core-normal.traeapi.us/api/ide/v1/text_to_image"

# Define assets to generate based on slide topics
ASSETS = {
    "icon_research": "minimalist 3d icon magnifying glass searching document blue and white isometric",
    "icon_user": "minimalist 3d icon user avatar profile with chat bubble blue and white isometric",
    "icon_plan": "minimalist 3d icon project roadmap flowchart checklist blue and white isometric",
    "icon_data": "minimalist 3d icon bar chart data analytics screen blue and white isometric",
    "icon_structure": "minimalist 3d icon abstract building blocks structure blue and white isometric",
    "icon_process": "minimalist 3d icon gears and arrows process workflow blue and white isometric",
    "icon_brain": "minimalist 3d icon artificial intelligence brain circuit blue and white isometric",
    "icon_robot": "minimalist 3d icon friendly robot assistant head blue and white isometric",
    "bg_cover": "abstract futuristic technology background blue gradient curves 8k resolution subtle",
    "bg_tech": "subtle white and light gray geometric pattern background professional business"
}

def download_image(key, prompt):
    filename = f"asset_{key}.png"
    if os.path.exists(filename):
        print(f"Skipping {filename} (already exists)")
        return filename

    print(f"Generating {filename}...")
    try:
        # Use square for icons, landscape for backgrounds
        size = "square_hd" if "icon" in key else "landscape_16_9"
        url = f"{API_BASE}?prompt={prompt}&image_size={size}"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
            return filename
        else:
            print(f"Failed: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
    return None

if __name__ == "__main__":
    if not os.path.exists("assets"):
        os.makedirs("assets")
    
    os.chdir("assets")
    
    for key, prompt in ASSETS.items():
        download_image(key, prompt)
        time.sleep(1) # Be nice to API
