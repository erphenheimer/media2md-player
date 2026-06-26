from media2md.pipeline.transcriber import resolve_whisper, probe_known_local_profile

local = probe_known_local_profile()
print(f"本地配置: {local is not None}")
if local:
    print(f"  exe: {local['exe']}")
    print(f"  model_dir: {local['model_dir']}")

config = resolve_whisper()
print(f"解析配置 exe: {config.get('exe', 'not found')}")

print("Transcriber module OK")
