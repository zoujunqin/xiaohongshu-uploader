### 读取根目录外 douyin-downloader 下的 multiple_account_config.json 配置文件，每个文件夹路径可绑定多个小红书账号
### 可以设定定时发布几天（days_per_time）,一天发布几个视频（count_per_day），文件夹下发布过后的时候会写入数据库记录，不会重复发布
### 距离上次最新定时发布时间3天内才可继续执行定时发布，否则跳过，避免日期重复。如果没有记录，从执行程序时隔天定时发布
### 如果需要重新从头发布，需要清空数据库记录
### 设定一个账号最多一天只能发布3条视频，定时时间分别是早上9点，中午1点，晚上6点
### douyin-downloader 和 social-auto-upload 两个文件夹需要放置同一层级

### 需要进入python 虚拟环境
```python
.venv/Scripts/activate
```

### 运行多账号上传脚本, 读取根目录外 douyin-downloader 下的 multiple_account_config.json 配置文件
```python
py ./batch_upload_xiaohongshu.py
```

### 上面两步整合到了 run.py 脚本，可直接运行这个脚本实现上面两个步骤
```python
py run.py
```

### 清空发布记录缓存， multiple_account_config.json 配置文件不存在的 xiaohongshu_account 的账号发布记录都会被清除
```python
py ./clean_xiaohongshu_publish_log.py
```