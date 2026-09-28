import ue, time, re, sys
def open_persp():
    s = ue.snapshot("w1", 60)
    m = re.search(r'combobox \[pos=1507,109[^\]]*\] \[ref=\w+\]\s+button (?:\[\w+\] )*\[pos=1507,109[^\]]*\] \[ref=(\w+)\]', s)
    ue.click(m.group(1)); time.sleep(0.8)
    return ue.snapshot("", 40)
def set_ev(v):
    s = open_persp()
    i = s.find('text "EV100"')
    ref = re.search(r'slider \[pos=[^\]]*\] \[ref=(\w+)\]', s[i:]).group(1)
    ue.call(ue.SLATE, "Type", {"ref": ref, "text": str(v), "submit": True}); time.sleep(0.5)
    s = open_persp()
    i = s.find('text "EV100"'); val = re.search(r'text "([^"]+)"', s[i + 12:]).group(1)
    j = s.find('text "Поле зрения"'); fov = re.search(r'text "([^"]+)"', s[j + 20:]).group(1)
    ue.call(ue.SLATE, "PressKey", {"key": "Escape"}); time.sleep(0.3)
    return val, fov
if __name__ == "__main__":
    print(set_ev(sys.argv[1]))
