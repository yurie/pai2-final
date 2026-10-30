# Judge AI（CRANE+ V2）

ブラウザで利用者がクイズを出し、Ollamaが回答するROS 2アプリです。利用者が回答を正解・不正解と判定すると、Gazebo上のCRANE+ V2アームが対応する動作をします。

## 主な仕様

- ブラウザ画面のタイトルは「Judge AI」です。
- 利用者が問題を入力すると、Ollamaが回答と短い理由を返します。問題文は2000文字までです。
- 正誤は利用者が判定します。Web版ではAI自身による採点は行いません。
- 正解でアームを下げて戻す動作を2回、不正解でアームを左右に振る動作を行い、初期姿勢に戻します。
- 判定した問題数と正解数を表示します。リセットまたはWebサーバーの再起動で記録は消去されます。
- Ollamaの回答を画面に表示するにはOllamaとローカルモデルが必要です。

## 対応環境

- Ubuntu 24.04 LTS / ROS 2 Jazzy
- CRANE+ V2公式ROS 2パッケージとGazebo
- Python 3、`python3-yaml`、colcon
- Ollama（ブラウザ版の回答に必要）

## ROS 2パッケージの導入

CRANE+ V2パッケージと必要なツールをインストールします。

```bash
sudo apt update
sudo apt install ros-jazzy-crane-plus ros-jazzy-ros2-controllers python3-yaml python3-colcon-common-extensions
mkdir -p ~/pai2_final_ws/src
cp -r /path/to/pai2-final ~/pai2_final_ws/src/
cd ~/pai2_final_ws
source /opt/ros/jazzy/setup.bash
rosdep install -r -y -i --from-paths src
colcon build --symlink-install
source install/setup.bash
```

## 起動方法（Gazebo上で実行）

### 1. Gazeboとコントローラー

ターミナル1で公式Gazeboシミュレーションを起動します。

```bash
source /opt/ros/jazzy/setup.bash
source ~/pai2_final_ws/install/setup.bash
ros2 launch crane_plus_gazebo crane_plus_with_table.launch.py
```

### 2. モーションノード

ターミナル2でアーム制御ノードを起動します。

```bash
source /opt/ros/jazzy/setup.bash
source ~/pai2_final_ws/install/setup.bash
ros2 run pai2_final pai2_final_motion --ros-args -p use_sim_time:=true
```

Gazebo側でアームとグリッパーのros2_controlコントローラーが起動している必要があります。コントローラーが接続されていない場合、モーションノードは指令を送りません。

### 3. Ollamaとブラウザ

Ollamaをインストールし、モデルを取得してサービスを起動します（モデル取得時はネットワークが必要です）。

```bash
ollama pull qwen2.5:7b-instruct
ollama serve
```

ターミナル3でWebアプリを起動します。

```bash
source /opt/ros/jazzy/setup.bash
source ~/pai2_final_ws/install/setup.bash
ros2 run pai2_final pai2_final_web
```

ブラウザで <http://127.0.0.1:8000> を開きます。問題を入力してAIの回答を確認し、「正解」または「不正解」を選んでください。Ollamaに接続できない場合は画面にエラーが表示されます。

接続先の既定値は `OLLAMA_URL=http://localhost:11434`、使用モデルは `OLLAMA_MODEL=qwen2.5:7b-instruct`、タイムアウトは `OLLAMA_TIMEOUT=30` 秒です。Webサーバーは `WEB_HOST=127.0.0.1`、`WEB_PORT=8000` で待ち受けます。環境変数で変更できます。

## CLIクイズ（任意）

ブラウザ版とは別に、AIがクイズを作成し、利用者が回答するターミナル版も含まれています。既定では一般知識から5問出題します。Ollamaに接続できない場合は `data/fallback_quiz.json` の問題に切り替わります。

```bash
source /opt/ros/jazzy/setup.bash
source ~/pai2_final_ws/install/setup.bash
ros2 run pai2_final pai2_final_quiz
```

CLI版では `QUIZ_COUNT` で問題数、`QUIZ_CATEGORY` で出題カテゴリを変更できます。これらはブラウザ版には適用されません。Ollamaの接続設定には上記の `OLLAMA_URL`、`OLLAMA_MODEL`、`OLLAMA_TIMEOUT` を使います。

## 動作設定

`config/motions.yaml` で制御トピック、関節名、姿勢、速度時間を設定します。既定の関節名は公式CRANE+ V2の `crane_plus_joint1`〜`crane_plus_joint4` と `crane_plus_joint_hand` です。正解動作はアームを下げて戻す動作を2回行います。不正解動作は左右に振り、各移動に2秒かけた後、初期姿勢へ戻ります。`home` はGazebo起動時の姿勢（各関節0）です。

動作の待機にはシミュレーション時計を使います。Gazeboを一時停止すると動作も待機し、再開後に続行します。

コントローラーの接続確認例:

```bash
ros2 topic info /crane_plus_arm_controller/joint_trajectory
ros2 topic info /crane_plus_gripper_controller/joint_trajectory
ros2 topic echo /joint_states
```

## 制御上の制約

- モーションノードが受け付ける動作IDは `celebrate`、`shake_no`、`home` のみです。
- AIの回答文をモーション指令として実行しません。Web版では利用者の判定に応じた固定IDをROSトピックへ送ります。
- アームとグリッパーの指令は公式コントローラーの `JointTrajectory` トピックへ送ります。
- シミュレーションでの利用を想定した設定です。実機の安全性を保証するものではありません。

## Dockerでの起動（任意、Ubuntuホスト）

Docker EngineとDocker Compose pluginが必要です。Gazebo GUIをX11で表示するため、起動前にX11接続を許可します。

```bash
xhost +local:root
cd /path/to/pai2-final
docker compose build gazebo
docker compose up -d gazebo
```

Ollamaコンテナを使う場合は、別ターミナルでモデルを取得します。

```bash
cd /path/to/pai2-final
docker compose --profile ai up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b-instruct
```

ブラウザ版を起動します。

```bash
cd /path/to/pai2-final
docker compose run --rm web
```

ブラウザで <http://127.0.0.1:8000> を開いてください。終了後はコンテナを停止し、X11接続許可を取り消します。

```bash
docker compose down
xhost -local:root
```

Docker構成はROS 2 DDS discoveryとGazebo GUIのためhost networkingを使います。USBデバイスはコンテナに割り当てていません。
