# 프로젝트 검토 및 노션 자료

2026-11-15 기준으로 가져온 자료와 4번 역할 점검 결과다. 노션 원문은 당시 내용을 보존한 스냅샷이며, 최신 사용자 요청과 구현의 차이는 검토 리포트에 따로 정리한다.

- [자율 팀 운영 기준](../ORCHESTRATION.md)
- [최종 연구 리포트](ROLE4_FINAL_REPORT.md)
- [데이터·지도 인계 및 재생성](ROLE4_HANDOFF.md)
- [정류장 지도 HTML](../output/role4/station_map.html)
- [연구일지: 연구 질문·방법·결과·해석·한계](research/RESEARCH_LOG.md)
- [4번 역할 최종 점검 리포트와 실행 계획](ROLE4_REVIEW_AND_PLAN.md)
- [현재 모델 입력 검사 결과](evidence/network_audit_2026-11-15.json)
- [첨부 원본 대조 결과](evidence/source_data_audit_2026-11-15.json)
- [데이터 수집 및 전처리: 원문과 데이터 첨부 8개](notion/01_data_preprocessing.md)
- [주아 3번 업무: 원문과 수식 첨부](notion/02_jua_role3.md)

원본 CSV를 갱신하더라도 현재 `network.json`이 자동으로 바뀌지는 않는다. 최종 데이터 범위와 수요·거점 규칙을 확정한 뒤 `prepare.py`로 재생성하고, 모든 알고리즘이 같은 버전을 사용해야 한다.

이번 자료 정리에서는 학습 코드와 기존 모델 입력을 변경하지 않았고 GitHub 커밋·push도 하지 않았다.
