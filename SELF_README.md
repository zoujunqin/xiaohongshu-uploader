### 读取根目录外 douyin-downloader 下的 multiple_account_config.json 配置文件，每个文件夹路径可绑定多个小红书账号
### 可以设定定时发布几天（days_per_time）,一天发布几个视频（count_per_day），文件夹下发布过后的时候会写入数据库记录，不会重复发布
### 

### 需要进入python 虚拟环境
```python
.venv/Scripts/activate
```

### 运行多账号上传脚本, 读取根目录外 douyin-downloader 下的 multiple_account_config.json 配置文件
```python
py ./batch_upload_xiaohongshu.py
```

### 清空发布记录缓存， multiple_account_config.json 配置文件不存在的 xiaohongshu_account 的账号发布记录都会被清除
```python
py ./clean_xiaohongshu_publish_log.py
```