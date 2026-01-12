#!/bin/bash

# Place Analytics 실행 스크립트

echo "🚀 Place Analytics 시작..."

# Backend 시작
echo "📦 Backend 서버 시작..."
cd backend
pip install -r requirements.txt -q
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Frontend 시작
echo "🎨 Frontend 서버 시작..."
cd frontend
npm install -q
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ 서버 실행 완료!"
echo "   - Frontend: http://localhost:3000"
echo "   - Backend:  http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"
echo ""
echo "종료하려면 Ctrl+C를 누르세요"

# 종료 시 프로세스 정리
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT

wait
