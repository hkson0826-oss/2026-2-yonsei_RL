# 모델·발표 담당자용 데이터 인계

버전: `role4-bundle-1.0` / 기준일 2026-11-15. [설계 명세](research/DATA_REWARD_SPEC.md), [설정](../data/role4_config.json), [연구 결과](ROLE4_FINAL_REPORT.md)를 함께 확인한다.

추가 인계: [실제 도로 경로 24개](../data/routes/v1/routes.geojson), [동일 경로 비용·품질 표](../data/routes/v1/route_metrics.csv), [경로 원천·재현](research/SELECTED_ROUTES_METHOD.md), [보상 재검토](research/REWARD_EVIDENCE_REVIEW.md), [v2 보고·종료 계약](../data/reward_contract_v2.json).

지도에서 **저장된 실제 도로 경로**를 선택하거나 **저장 도로구간 전체 표시**를 켜면 캐시의 실제 도로선을 표시한다. 청록색 전체 표시는 서로 독립적인 대표 구간들이며 하나의 학습·최적화 노선이 아니다. 기존 통합 JSON은 보존하고 생성 HTML에 선택 경로 자료와 보상 해석 계약을 별도 필드로 추가했다.

## 먼저 알아야 할 준비 상태

공식 ARS 지역 코드 13의 정류장 464개를 모두 보존했다. 5–10월 수요는 매월 454개 관측·10개 결측이며, 방향별 도로비용은 292개 내부에서만 관측됐다. 전체 기준의 도로거리 129,860쌍은 `null`이다. **전체 지역의 모델 입력 준비 상태는 false다.** 지도와 데이터 참조 완성은 학습 준비·최적 노선·실제 운행 검증과 다르다.

이 범위는 2026-09-02 공식 코드 목록이다. 모든 좌표의 행정구역 폴리곤 포함이나 현재 운영 상태를 별도 판정한 목록이 아니다. 지도와 인계 자료를 ‘464개 완전 노선 학습 입력’이라고 소개하면 안 된다.

## 산출물

| 파일 | 용도 |
| --- | --- |
| [role4_bundle.json](../data/processed/role4_bundle.json) | 지도와 소비자가 함께 사용하는 통합 참조 자료 |
| [stop_master.csv](../data/processed/stop_master.csv) | 464개 정류장, 수요 점수, 거점, 품질·정차 정책 플래그 |
| [ridership.csv](../data/processed/ridership.csv) | 464개×6개월 원천 합계·일평균·고정 척도 점수 |
| [hub_mapping.csv](../data/processed/hub_mapping.csv) | 200/300/500m별 모든 정류장 매핑, 후보 그룹과 최종 단일 귀속 |
| [hub_sensitivity.json](../data/processed/hub_sensitivity.json) | 반경별 배정·중첩·미배정·반경 내 후보 부재의 구별 |
| [road_distances_full.json](../data/processed/road_distances_full.json) | 464개 공통 인덱스의 부분 도로 행렬; 미관측 null 유지 |
| [road_snap.csv](../data/processed/road_snap.csv) | 원본 스냅 보유·품질 상태 |
| [diagnostic_259.json](../data/processed/diagnostic_259.json) | 비중앙차로·수요 관측·원본 거리 보유 진단 부분 집합; 전체 대체안 아님 |
| [검증 근거](evidence/role4_build_validation.json) | 원본 해시, 재계산 개수, 단위·정의 검사 |

CSV는 UTF-8 BOM이며 결측 수치는 빈 칸이다. ID·ARS 번호는 문자열로 읽는다. 자동 숫자 변환으로 ARS 번호의 선행 0을 잃지 않도록 한다. JSON의 수치는 저장 단계에서 반올림하거나 검증값을 잘라내지 않았다.

## 재생성

Python 3.9 이상, 아래 데이터 변환은 표준 라이브러리만 사용한다. `pytest`는 검증용 의존성이다. 원본 자료가 이미 있다면 네트워크 없이 다시 만들 수 있다.

```powershell
python scripts/build_role4_roads.py
python scripts/build_role4_data.py
python scripts/build_role4_map.py
python -m pytest tests -q
```

지도 DOM 기능 검증은 `npm ci` 후 `npm run test:map`으로 실행한다. 14개 검사는 실제 브라우저 화면 배치·스크린샷 검수가 아니라 오프라인 DOM 동작 검사다. 선택적인 정적 미리보기는 [map_preview.png](../output/role4/map_preview.png)다.

선택 경로 확장 후 DOM 검사는 20개다. [도로선 정적 미리보기](../output/role4/road_route_preview.png)는 실제 경로 좌표를 그린 그림이며 브라우저 화면 캡처는 아니다. 선택 경로의 재생성·품질 확인은 외부 호출 없이 다음을 실행한다.

```powershell
python scripts/fetch_selected_routes.py --offline
python scripts/validate_route_geometry.py
python scripts/audit_reward_tradeoffs.py
python scripts/build_role4_map.py
```

`--fetch`는 정책 제한을 갖춘 별도 취득 모드이며 기본 재생성에는 필요하지 않다. 공개 서버를 학습 도중 호출하지 않는다. 프로파일 `routability` 가중치와 추정시간을 구별하며, 새 도로 자료를 기존 292개 행렬에 섞지 않는다.

## 보상 v2 연결의 의미

주 보고는 원시 하차 활동·고유 근접 그룹·거리·추정시간·정차 수·가용성이다. 이는 DQN에 바로 넣을 단일 보상이 아니며 선호·가중합·제약의 연결은 외부 모델 담당자가 명시해야 한다. 기존 0.5·0.2는 미보정 정책 기준안이고, 자동차 시간 항을 임의로 더하지 않았다. optional STOP은 0단계 경로도 허용하는 수학적 대안으로 명시했으며, 실제 비어 있지 않은 버스 노선에 필요한 최소 서비스 조건은 자료로 확정하지 못했다. 기존 모델의 강제 연장 종료는 변경하지 않았다.

지도 파일 경로는 `output/role4/station_map.html`이다. 지도 빌드는 별도 스크립트이며 데이터 빌드는 지도를 자동으로 학습하거나 노선을 생성하지 않는다.

공식 월별 수요를 다시 집계할 필요가 있을 때만 `python scripts/fetch_role4_ridership.py`를 사용한다. 무료 공개 파일이며 로컬 압축 원본이 있으면 재사용한다. [월별 출처·해시](../data/reference/ridership_provenance.json), [공간 출처](../data/reference/spatial_sources.json)를 보존한다. 누락 자료 확보를 위해 비용·새 API 키를 전제하지 않는다.

## 통합 JSON 계약

- `ids`: 사전식 오름차순의 정류장 ID 문자열 464개.
- `stops[i]`, `months[m]`의 배열, `distances_m[i][j]`는 모두 같은 `ids` 순서다.
- `distances_m[i][j]`: i→j 원본 방향별 도로거리(m). `null`은 자료 미확보이며 이동 불가 또는 0m가 아니다.
- `months[m]`: `days`, `split`, `alight`, `has_source_record`, `daily`, `score`. `alight`는 월간 원천 합계, `daily`는 그 월 달력 일수로 나눈 값, `score`는 같은 학습 M으로 나눈 값이다.
- `hubs`: 원천 정보가 붙은 기준점 22개다. 그룹 ID는 16개이며 같은 역 여러 기준점이 있을 수 있다.
- `hub_assignments_by_radius['300'][i]`: 기본 반경에서의 i 정류장 매핑. `200`, `500`도 같은 순서다.
- `config`, `summary`, `readiness`, `provenance`: 산식·가정·결측·파일 해시와 준비 상태를 전달한다.

주요 정류장 필드:

| 필드 | 의미 |
| --- | --- |
| `station_id`, `ars_id`, `station_name` | 공식 ID·ARS·정류장명 |
| `latitude`, `longitude` | WGS84 위·경도 |
| `demand_daily_train` | 학습 월 총하차량/123일; 하나라도 결측이면 null |
| `demand_score_train` | `demand_daily_train / M`; M은 전체 관측 학습 모집단에서 고정 |
| `complete_train` | 학습 4개월 원천 기록이 모두 있음 |
| `hub_id`, `hub_name` | 300m 내 최근접 그룹 하나; 없으면 null |
| `hub_distance_m`, `hub_anchor_id` | 직선 근접성의 계산 근거 |
| `hub_candidates` | 반경 내 모든 그룹; 복수 보너스 지급 지시가 아님 |
| `road_source_covered` | 원본 도로자료 보유 여부; 대각선 0만으로 참 판정하지 않음 |
| `distance_quality`, `quality_flags` | 원본 스냅 주의·미확보·중앙차로·0m 구간 표시 |
| `candidate_eligible_by_policy` | 중앙차로 제외 연구 가정을 통과; 법적 운행·정차 인증 아님 |
| `diagnostic_subset_eligible` | 정차 가정 통과+수요 관측+원본 거리 보유; 총 259개 |

`reference_complete=true`는 공식 목록의 보존을 뜻한다. `demand_full`, `road_full`, `full_district_model_ready`, `operational_verified`, `bus_drivability_verified`는 별개다. 현재 모두 false이며 실제 버스 운행 검증을 수행하지 않았다.

## 수요와 거점 해석

수요는 오전 07시대+08시대의 월간 하차 실적이다. 학습은 5–8월 총량/123일이며 정규화 M은 중앙차로를 포함한 454개 전체에서 계산한 `104278/123 ≈ 847.7886178861788`이다. 필터·월·반경을 바꾸어도 M은 고정한다. 검증 점수가 1보다 커도 저장값은 잘라내지 않는다. 실제 0인 한 정류장과 미관측 10개를 구분한다.

거점은 직선 근접성의 대리 지표다. 실제 출입구·도보 횡단·장벽을 검증한 값이 아니다. 각 그룹의 모든 기준점 중 최단거리로 그룹을 비교하고, 반경 안의 최근접 그룹 하나에 귀속한다. 동률이면 그룹 ID와 기준점 ID로 결정한다. 같은 역의 호선은 그룹을 공유하고 신촌 2호선·경의중앙선 신촌은 별개다.

300m는 재현 가능한 프로젝트 스크리닝 가정이다. 반경별 배정 정류장은 200m 61개, 300m 103개, 500m 186개이며 500m에서는 36개가 복수 그룹 후보를 갖는다. `unassigned_group_ids`는 최종 귀속 없음, `no_candidate_group_ids`는 반경 내 후보 자체가 없음으로 의미가 다르다.

## 보상 연결 시 주의

설명식은 `수요 점수 + 신규 그룹 0.5 - 거리(km)×0.2`다. 최초 출발은 보상이 없고 출발 그룹은 이미 방문한 것으로 처리한다. 이후 같은 그룹의 다른 정류장에 가도 그룹 보너스는 다시 주지 않는다. 자유 종점 기본안은 마지막 정차 수요도 포함한다. 계수는 최적화·화폐편익 추정 결과가 아니라 명시적 선호다.

수요 또는 해당 방향 도로거리가 null이면 보상 산술을 정의하지 않는다. 정차 정책에 따라 제외되는 지점과 같은 정류장 재정차는 유효 행동과 구별한다. UI에서 보이는 산술 참고는 모델 학습·유효한 전체 노선 생성 결과가 아니다.

## 기존 모델과의 비호환 및 외부 담당 과제

기존 `train.py`는 월별 일평균의 단순평균을 다시 계산하므로 새 `demand_score_train`을 자동으로 사용하지 않는다. 원천 월 배열만 교체하면 이번 기간 일평균·전역 고정 분모가 적용되지 않는다. 기존 `hub` 문자열과 새 `hub_id=null`도 다르다. **null이 있는 부분 거리 행렬을 기존 numeric-only 로더에 그대로 넣으면 안 된다.** 모델 연결·학습 코드 수정은 이번 작업 범위에서 수행하지 않았다.

외부 모델 담당자는 필요한 입력을 명시적으로 연결하고, 전체 도로거리·결측 수요를 확보하거나 실제 사용 범위를 별도로 선언해야 한다. 고정 종점을 쓰면 종료 ID·거리 예산·유효 행동 조건을 별도 명세해야 한다. 부분 집합의 결과를 전체 지역 결과로 보고하지 않는다. 학습·최적 노선·성능 비교는 이 인계 자료에서 입증하지 않았다.
