# legal-ease
An AI-powered tool for translating legalese into plain English.## Category Eval (optional)

Our enhanced evaluation system tests both category classification accuracy and translation quality using GPT-4 as a judge.

**Current Performance:**
- **Category Accuracy: 100%** (23/23 test cases)
- **Translation Quality: 4.35/5.0** average
- **Quality Distribution:** 95% of translations rated "Very Good" (4/5) or "Excellent" (5/5)

1. Make sure your backend server is running.
2. Run the enhanced eval script:
   ```bash
   python backend/enhanced_eval.py
   ```
   This will test the model's ability to categorize legalese, evaluate translation quality, and print comprehensive accuracy results.or legal professionals, developers, and the legally curious.

## Live Demo

[Try Legal Ease here!](https://legal-ease-welcome.onrender.com/)

![Example: Legalese to Plain English](./frontend/public/example.png)

## Prerequisites

- Python 3.8+
- Node.js & npm
- An OpenAI API key ([get one here](https://platform.openai.com/account/api-keys))

## Backend Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Rob-Kornblum/legal-ease.git
   cd legal-ease
   ```

2. **Create a virtual environment and activate it:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Set your OpenAI API key as an environment variable by creating a .env file in the backend directory:**
   ```bash
   OPENAI_API_KEY=sk...
   ```

5. **Run the backend:**
   ```bash
   uvicorn backend.main:app --reload
   ```

## Frontend Setup

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install frontend dependencies:**
   ```bash
   npm install
   ```

3. **Start the React app:**
   ```bash
   npm start
   ```

   The app will open at [http://localhost:3000](http://localhost:3000).

## Usage

1. Enter a legalese phrase in the text area, **or click "Auto-Generate Example" to fill the input with a random sample legalese phrase.**
2. Click "Translate".
3. View the plain English translation below.

The "Auto-Generate Example" button helps you quickly test the app with realistic legalese

## Troubleshooting

- If you see CORS errors, ensure the backend has CORS middleware enabled for `http://localhost:3000`.
- Make sure both backend and frontend servers are running.

## Category Eval (optional)

1. Make sure your backend server is running.
2. Run the eval script:
   ```bash
   python backend/enhanced_eval.py
   ```
   This will test the model’s ability to categorize legalese and print accuracy results.

## Running Tests Locally

1. **Ensure your virtual environment is activated** (see Backend Setup above).

2. **Install all dependencies** (if you haven’t already):
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Run the test suite from the backend directory:**
   ```bash
   pytest
   ```

4. **(Optional) View detailed output:**
   ```bash
   pytest -v
   ```

If you add or modify tests, simply re-run `pytest` to check your changes.