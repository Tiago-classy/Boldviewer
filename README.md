# BOLD-VIEWER

BOLD-VIEWER is a web application designed to provide an intuitive interface for browsing and viewing multimedia content. It supports features like user authentication, file browsing, and multimedia playback.

## Features
- User authentication system.
- Multimedia file browsing and viewing.
- Integration with AWS S3 for file storage.
- Responsive design for various devices.

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

3. Create a virtual environment and activate it:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

4. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Start the application:
   ```bash
   python app.py
   ```

2. Open your web browser and navigate to `http://127.0.0.1:5000`.

3. Alternatively, you can use Docker to build and run the application:
   ```bash
   docker build -t bold-viewer .
   docker run -p 5000:5000 bold-viewer
   ```

## Contributing
Contributions are welcome! Please fork the repository and submit a pull request.

## License
This project is licensed under the MIT License.
