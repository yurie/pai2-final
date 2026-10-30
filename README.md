# CRANE+ V2 PAI2 Final

日本語クイズに回答すると、正解ではグリッパーを開いてバンザイ、不正解ではアームを左右に振るROS 2 Pythonアプリです。初期設定はシミュレーション向けです。

## 対応環境

- Ubuntu 24.04 LTS / ROS 2 Jazzy
- CRANE+ V2公式ROS 2パッケージのGazebo構成
- ブラウザ版の問題生成にOllamaとローカルモデルが必要

## ROS 2パッケージの導入

```bash
sudo apt update
sudo apt install ros-jazzy-crane-plus ros-jazzy-ros2-controllers python3-yaml
mkdir -p ~/pai2_final_ws/src
cp -r /path/to/pai2-final ~/pai2_final_ws/src/
cd ~/pai2_final_ws
source /opt/ros/jazzy/setup.bash
rosdep install -r -y -i --from-paths src
colcon build --symlink-install
source install/setup.bash
```

## Gazeboとコントローラー

ターミナル1で公式Gazeboシミュレーションを起動します。

```bash
source /opt/ros/jazzy/setup.bash
source ~/pai2_final_ws/install/setup.bash
ros2 launch crane_plus_gazebo crane_plus_with_table.launch.py
```

公式パッケージのGazebo launchがアーム用のros2_controlコントローラーを起動することを確認してください。公式サンプルではGazebo上のグリッパー制御を想定し、`use_sim_time:=true`を指定します。

ターミナル2でモーションノードを起動します。

```bash
source /opt/ros/jazzy/setup.bash
source ~/pai2_final_ws/install/setup.bash
ros2 run pai2_final pai2_final_motion --ros-args -p use_sim_time:=true
```

## ブラウザ版クイズ（AI回答者）

別ターミナルでOllamaを起動してモデルを用意します。初回のモデル取得にはネットワークが必要です。

```bash
ollama pull qwen2.5:7b-instruct
ollama serve
```

```bash
source /opt/ros/jazzy/setup.bash
source ~/pai2_final_ws/install/setup.bash
ros2 run pai2_final pai2_final_web
```

ブラウザで <http://127.0.0.1:8000> を開き、問題を入力してください。Ollamaが回答と短い理由を返します。あなたが「正解」または「不正解」を選ぶと、対応するアーム動作を送り、得点を記録します。Ollamaに接続できない場合は回答を表示できません。ポートや待受アドレスは `WEB_PORT`（既定 `8000`）と `WEB_HOST`（既定 `127.0.0.1`）で変更できます。

## Ollama（ターミナル版では任意）

別ターミナルでCLI版を起動します。CLI版はOllamaに接続できない場合に `data/fallback_quiz.json` を使います。

```bash
source /opt/ros/jazzy/setup.bash
source ~/pai2_final_ws/install/setup.bash
export OLLAMA_MODEL=qwen2.5:7b-instruct
export OLLAMA_URL=http://localhost:11434
export OLLAMA_TIMEOUT=30
export QUIZ_COUNT=5
export QUIZ_CATEGORY=科学
ros2 run pai2_final pai2_final_quiz
```

## 動作設定

`config/motions.yaml`でROSトピック、関節名、各プリセット、速度時間を設定します。既定の腕関節名は公式CRANE+ V2の `crane_plus_joint1`〜`crane_plus_joint4`、グリッパーは `crane_plus_joint_hand` としています。`home`はGazebo起動時の姿勢（各関節0）で、正解時は腕を下げて戻す動作を2回行い、不正解時は左右の振りを1回2秒で行った後にこの姿勢へ戻します。動作の待機はシミュレーション時計に合わせるため、Gazeboを一時停止すると動作も待機し、再開後に続行します。

接続確認例:

```bash
ros2 topic info /crane_plus_arm_controller/joint_trajectory
ros2 topic info /crane_plus_gripper_controller/joint_trajectory
ros2 topic echo /joint_states
```

シミュレーション以外に接続しないでください。初期値は学習用の叩き台で、実機安全を保証しません。

## 制御の仕組みと制約

- Motion Controllerは `/pai2_final/motion` の文字列から `celebrate`、`shake_no`、`home` だけを許可します。
- アーム動作は公式controllerの `JointTrajectory` トピックに送ります。
- Gazebo構成でコントローラーが利用できない場合、指令は送信せずログにエラーを出します。
- 問題生成・自由記述採点はOllamaのJSONモードを使います。利用者回答が不正JSONや制御入力として扱われることはありません。
- 初期の正解判定は許容回答との文字列照合を優先します。LLMの意味判定は照合に失敗した場合だけ使います。

## Dockerでの起動（Ubuntuホスト）

Docker EngineとDocker Compose pluginをUbuntuに用意してください。Gazebo GUIをホストに表示するため、現在のX11セッションからコンテナへの接続を一時的に許可します。

```bash
xhost +local:root
cd /path/to/pai2-final
docker compose build gazebo
docker compose up -d gazebo
```

別ターミナルでローカルLLMサービスを起動し、モデルを取得します。モデル取得は初回のみネットワークを使います。

```bash
cd /path/to/pai2-final
docker compose --profile ai up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b-instruct
```

ブラウザ版クイズを起動します。

```bash
cd /path/to/pai2-final
docker compose run --rm web
```

ブラウザで <http://127.0.0.1:8000> を開いてください。

ブラウザ版ではOllamaとモデルが必要です。Ollamaへ接続できない場合は画面にエラーが表示されます。

停止後、X11接続許可を取り消します。

```bash
docker compose down
xhost -local:root
```

`docker-compose.yml`はROS 2 DDS discoveryとGazebo GUIを扱うためhost networkingを使います。Docker内のアーム指令は許可済みの動作IDに限定されています。USBデバイスはコンテナへ割り当てていません。
