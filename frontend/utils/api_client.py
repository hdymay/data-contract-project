"""
API 클라이언트
"""
import requests
import streamlit as st
from typing import Optional, Dict, Any

class APIClient:
    """FastAPI 백엔드와 통신하는 클라이언트"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    def analyze_contract(self, file, contract_type: str) -> Optional[Dict[str, Any]]:
        """계약서 분석 요청"""
        try:
            # 파일 업로드
            files = {"file": file}
            data = {"contract_type": contract_type}
            
            response = requests.post(
                f"{self.base_url}/api/analysis/analyze",
                files=files,
                data=data,
                timeout=300  # 5분 타임아웃
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"API 오류: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            st.error(f"연결 오류: {e}")
            return None
    
    def get_analysis_status(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """분석 상태 조회"""
        try:
            response = requests.get(f"{self.base_url}/api/analysis/{analysis_id}/status")
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except requests.exceptions.RequestException:
            return None
    
    def download_report(self, analysis_id: str) -> Optional[bytes]:
        """리포트 다운로드"""
        try:
            response = requests.get(f"{self.base_url}/api/report/{analysis_id}/download")
            
            if response.status_code == 200:
                return response.content
            else:
                return None
                
        except requests.exceptions.RequestException:
            return None
