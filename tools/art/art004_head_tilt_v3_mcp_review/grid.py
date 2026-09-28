import ue, time, re
def toggle_grid():
    s = ue.snapshot("w1", 60)
    m = re.search(r'combobox \[pos=1848,109[^\]]*\] \[ref=\w+\]\s+button (?:\[\w+\] )*\[pos=1848,109[^\]]*\] \[ref=(\w+)\]', s)
    ue.click(m.group(1)); time.sleep(0.8)
    s = ue.snapshot("", 40)
    i = s.find('generic "Решётка')
    blk = s[i:i + 400]
    ref = re.search(r'\[ref=(\w+)\]', blk).group(1)
    cb = re.search(r'checkbox \[(\w+)\]', blk)
    state = cb.group(1) if cb else None
    ue.click(ref); time.sleep(0.5)
    ue.call(ue.SLATE, "PressKey", {"key": "Escape"}); time.sleep(0.3)
    return state
if __name__ == "__main__":
    print("grid state before toggle:", toggle_grid())

def ensure_grid_off():
    st = toggle_grid()
    if st == "unchecked":
        toggle_grid()
        return "was_off"
    return "turned_off"
