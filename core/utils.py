import os

def check_assets():
    if not os.path.exists("assets"):
        os.makedirs("assets")
    
    required = ["focus.gif", "break.gif", "alert.gif"]
    missing = [f for f in required if not os.path.exists(os.path.join("assets", f))]
    
    if missing:
        print(f"⚠️ 缺少素材: {missing}。已生成占位文件。")
        for f in missing:
            with open(os.path.join("assets", f), "w") as dummy: dummy.write("placeholder")