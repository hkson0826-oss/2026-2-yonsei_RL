# 연세대 연계 마을버스 노선 설계

팀 정제본에서 정류장 ID가 112로 시작하는 서대문구 정류장 282곳을 모두 사용한다.
`network.json`은 정류장(01), 월별 하차량(02), 방향별 도로거리 ZIP(11)을 ID로 연결한 입력이다. 원본이 바뀌면 `python3 prepare.py "/path/to/data-folder"`로 다시 생성한다. 기존 정제본의 마을버스 정차 제한 표시가 있는 23곳도 실험 후보에 포함된다.
배경 지도는 OpenStreetMap이다.

## 실행

Python 3.9 이상에서 Q-learning, SARSA, 기준 전략을 바로 실행할 수 있다.
DQN은 PyTorch가 필요하다. GPU 머신에는 CUDA를 지원하는 PyTorch를 설치한다.

```sh
python3 train.py --algo q-learning --episodes 5 --rounds-per-episode 20
```

VS Code에서 `train.py`를 열고 **Run Python File**을 눌러도 된다. 실행하면 기본 브라우저가 열리고 버스 아이콘이 학습 중 생성한 경로를 순서대로 재생한다. 브라우저가 자동으로 열리지 않으면 터미널에 출력된 주소를 연다. 학습 종료 후에도 지도를 볼 수 있으며, 터미널에서 Ctrl+C를 누르면 종료한다. 지도 타일과 Leaflet에는 인터넷 연결이 필요하다. 선과 아이콘의 이동은 정류장 좌표를 직선으로 연결하며, 보상에 쓰는 거리는 도로거리 행렬 값이다.

```sh
python3 train.py --algo sarsa --steps 3000 --out runs/sarsa
python3 -m pip install -r requirements.txt
python3 train.py --algo dqn --steps 5000 --device cpu --out runs/dqn
python3 train.py --algo random --episodes 5 --rounds-per-episode 20 --out runs/random
python3 train.py --algo greedy --episodes 1 --rounds-per-episode 1 --out runs/greedy
python3 train.py --algo dp --max-stops 12 --episodes 1 --rounds-per-episode 1 --out runs/dp
```

지도는 현재 실행의 출력 폴더를 자동으로 읽는다. 실험별로 별도의 `--out`을 지정한다. GPU 서버나 일괄 실험에서는 `--no-viewer`를 붙이면 학습이 끝난 뒤 바로 종료된다.
대규모 비교 시 세 RL 방식에 각각 동일한 `--steps 200000`, 설정, 시드 목록을 적용한다. CUDA에서는 `--device cuda`를 사용한다.
DP 최적해와 비교할 때는 모든 방식에 같은 `--max-stops`를 지정한다. 후보 제한은 후보표 앞부분을 사용한다.

## 환경과 보상

- 상태는 현재 정류장, 방문 집합, 남은 거리다. 다음 정류장을 선택하면 방향별 도로거리를 차감한다.
- 거리를 더하면 상한을 넘는 정류장과 이미 방문한 정류장을 제외한다. 가능한 이동이 없으면 현재 정류장에서 종료한다.
- 수요 점수는 5–8월 오전 7–9시 월간 하차량을 월 일수로 나누고, 월별 일평균의 평균을 후보 내 최댓값으로 나눈다. 9–10월 값은 학습된 노선의 월별 경유지 하차량 평가에 사용한다.
- 점수 = 경유 정류장별 정규화 하차량 + 최초 거점 방문당 2점 − 도로거리 1km당 0.2점. 출발점 하차 점수는 제외하고 마지막 정류장 하차 점수는 포함한다.
- 이동 가능한 일반 정류장 중 `--start-seed`로 5곳을 한 번 뽑아 `starts.json`에 시드와 ID를 저장한다. 같은 후보와 거리 상한에서 같은 출발 시드를 사용하면 재현된다. `--seed`는 학습 난수용이다.
- 한 라운드에 저장한 출발점 5곳 중 하나를 뽑아 경로 1개를 생성한다. 기본 20라운드가 한 에피소드이며 기본 5에피소드에서 학습을 종료한다. 종점은 마지막으로 선택한 정류장이다. 기본 거리 상한은 6,000m이며 `--budget-m`으로 설정한다.
- 신촌·이대·아현·연대앞 각 거점에 처음 정차할 때 보너스를 준다. 거점의 대표 정류장 ID는 `prepare.py`에서 관리한다.
- 하차량은 기존 이용 실적이다. 거리 자료는 실제 마을버스의 회전 및 정차 가능성까지 검증한 값으로 해석하지 않는다.

## 비교 방식과 출력

Q-learning과 SARSA는 동일한 상태 표현으로 각각 다음 상태의 최대 Q와 다음에 실제 선택한 행동의 Q를 사용한다. DQN은 128–128 MLP, 경험 재생, 타깃 네트워크와 유효 행동 마스크를 사용한다. 세 방법 모두 `--exploration epsilon-greedy` 또는 `--exploration greedy`를 선택한다. 기준 탐욕법은 이용량 점수와 신규 거점 보너스의 합을 이번 이동거리로 나눈다. DP는 작은 후보 집합에서 벨만 최적값을 메모이제이션한다.

`history.jsonl`에는 모든 경로를, `episode_winners.json`에는 에피소드별 최고 보상 경로를 저장한다. 지도에서 **최고 보상 노선 보기**를 누르면 최신 에피소드 우승 경로를 재생한다. 모델은 `model.pt` 또는 `q_table.json`에 저장된다.
`--steps`를 지정하면 전이 예산에 맞춰 학습하고 마지막으로 진행 중이던 노선을 완성한다. 마지막 에피소드는 설정한 라운드 수보다 짧을 수 있다.

병렬 실험 명령은 [PARALLEL_EXPERIMENTS.txt](../PARALLEL_EXPERIMENTS.txt)에 정리했다.
학습 종료 후 **🏆 전체 최고 노선**을 누르면 실행 전체에서 보상이 가장 높았던 경로를 지도에 고정한다. 화면 없이 돌린 실험도 `python3 train.py --replay runs/dqn-42`로 열 수 있다.
