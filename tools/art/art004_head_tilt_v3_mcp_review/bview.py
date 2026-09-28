import json, subprocess, sys
def view(params, shot=None, size=1600):
    code = "PARAMS = " + repr(json.dumps(params)) + "\n" + open("C:/tmp/a1v3/blender/b6_view.py", encoding="utf-8").read()
    open("C:/tmp/a1v3/blender/_b6_run.py", "w", encoding="utf-8").write(code)
    c = "C:/Users/ren/.claude/mcp-servers/clients/blender_mcp.py"
    print(subprocess.run([sys.executable, c, "exec", "C:/tmp/a1v3/blender/_b6_run.py"], capture_output=True, text=True).stdout[-400:])
    if shot:
        print(subprocess.run([sys.executable, c, "shot", shot, str(size)], capture_output=True, text=True).stdout[-300:])
