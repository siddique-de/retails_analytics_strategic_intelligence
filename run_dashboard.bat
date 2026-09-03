@echo off
echo Starting Enterprise Retail Analytics Dashboard...
echo Open your browser at: http://localhost:8501
echo.
C:\Python\python.exe -m streamlit run app.py --server.port 8501
pause
