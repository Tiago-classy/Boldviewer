# BOLD-VIEWER

BOLD-VIEWER is a web application designed to provide an intuitive interface for browsing and viewing multimedia content. It supports features like user authentication, file browsing, and multimedia playback.

## Features
- User authentication system.
- Multimedia file browsing and viewing.
- Integration with AWS S3 for file storage.
- Responsive media library with search, file-type filters, sorting, and remembered grid/list views.
- File sizes and modification dates from S3 listing metadata.
- Image fit/actual-size controls, fullscreen viewing, and native video playback.
- Lazy previews, bounded background thumbnail generation, and private browser caching.
- Paged S3 browsing for large folders.

## Project Structure
- `app.py`: Entry point for the application.
- `config.py`: Configuration settings for the application.
- `routes/`: Contains route definitions for the application.
- `static/`: Static assets like CSS, JavaScript, and images.
- `templates/`: HTML templates for rendering views.
- `utils/`: Utility scripts for various functionalities.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/BOLD-VIEWER.git
   ```

2. Navigate to the project directory:
   ```bash
   cd BOLD-VIEWER
   ```

3. Use Python 3.11–3.13 (matching the pinned dependencies). Create a virtual environment and activate it:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

4. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

Video thumbnails require FFmpeg on the server. The Docker image already includes it.

Configure the values in `.env_example` in your local `.env`, including the bucket and region.

## Usage

1. Start the application:
   ```bash
   SESSION_COOKIE_SECURE=false python app.py
   ```

2. Open your web browser and navigate to `http://127.0.0.1:5000`.

3. Alternatively, you can use Docker to build and run the application:
   ```bash
   docker build -t bold-viewer .
   docker run -p 5000:5000 bold-viewer
   ```

## Verification

Run the offline regression suite after installing dependencies:

```bash
python -m unittest discover -v
```

The suite uses mocked S3 responses and a temporary thumbnail cache; it does not access your bucket. A real video-frame integration check runs when FFmpeg is installed.

## Media pipeline

Directory pages contain up to 120 S3 entries and are cached for 15 seconds per worker. Use **Next page** to continue through a large folder; search and type filters apply to the loaded page. Sort by name, latest modification, or size without another network request. Modification dates appear in list view. View preferences are stored in the browser. The **Reload** button bypasses the directory cache.

Thumbnail work runs in two background workers per application process, with at most 32 pending jobs. File locks prevent duplicate generation across processes, and completed JPEGs are published atomically. Failures have a 60-second retry cooldown; **Retry previews** allows an explicit retry within the same queue limits. Images over 50 MB retain their original download and preview links but skip thumbnail generation. Videos use FFmpeg seeking and range reads instead of loading the whole video into Python memory. Thumbnail generation has a 30-second video timeout; unsupported codecs show a fallback.

Completed thumbnails have private browser caching; incomplete placeholders and authenticated pages are not cached. The full-size player uses native browser controls and loads only video metadata before playback. Production cookies remain HTTPS-only; the local command above enables HTTP cookies for development.

## Contributing
Contributions are welcome! Please fork the repository and submit a pull request.

## License
This project is licensed under the MIT License.
