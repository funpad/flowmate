import openai
import json
import time
from core.config import CONFIG, MOCK_MODE

class AIGuardian:
    def __init__(self):
        self.client = None
        self.reload_client()
        self.current_profile = None 

    def reload_client(self):
        api_key = CONFIG.get("api_key")
        base_url = CONFIG.get("base_url")
        if not MOCK_MODE and api_key:
            self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = None

    def smart_planner(self, user_goal):
        if MOCK_MODE or not self.client:
            time.sleep(1)
            return [{"step": f"开始 {user_goal}", "duration": 25, "break": 5}]
        
        prompt = f"""
        用户目标："{user_goal}"。
        拆解为3-5个步骤。要求：动态时长(5-45m)，智能休息(3-10m)，第一步简单。
        JSON: {{ "tasks": [ {{ "step": "任务名", "duration": int, "break": int }} ] }}
        """
        try:
            res = self.client.chat.completions.create(model=CONFIG.get("model"), messages=[{"role": "user", "content": prompt}], temperature=0.7, response_format={"type": "json_object"})
            data = json.loads(res.choices[0].message.content)
            return data.get("tasks", data.get("steps", []))
        except: return []

    def create_task_profile(self, user_goal):
        if MOCK_MODE or not self.client:
            self.current_profile = {"allowed": ["code", "python"]}
            return
        prompt = f"任务:'{user_goal}'。5-8个必要白名单关键词。JSON:{{'allowed':[]}}"
        try:
            res = self.client.chat.completions.create(model=CONFIG.get("model"), messages=[{"role": "user", "content": prompt}], temperature=0.2, response_format={"type": "json_object"})
            self.current_profile = json.loads(res.choices[0].message.content)
        except: self.current_profile = {"allowed": []}

    def judge(self, user_goal, active_window, process_name):
        if not self.current_profile: return False, "加载中..."
        txt = (active_window + process_name).lower()
        sys_white = ["explorer", "searchapp", "new tab", "新标签页"]
        if any(s in txt for s in sys_white): return False, "System"
        for w in self.current_profile.get("allowed", []):
            if w.lower() in txt: return False, f"Allowed: {w}"
        if MOCK_MODE or not self.client: return True, "[模拟] 异常"
        
        is_strict = CONFIG.get("strict_mode", False)
        role = "严厉魔鬼教官" if is_strict else "客观中立监督员"
        prompt = f"""
        角色:{role} 任务:"{user_goal}" 行为:"{active_window}"({process_name})
        未白名单。判断:1.明显分心->true 2.其他->false. JSON:{{ "is_distracted": bool, "reason": "str" }}
        """
        try:
            res = self.client.chat.completions.create(model=CONFIG.get("model"), messages=[{"role": "user", "content": prompt}], max_tokens=60, response_format={"type": "json_object"})
            data = json.loads(res.choices[0].message.content)
            return data.get("is_distracted", False), data.get("reason", "")
        except: return False, "Err"

    def generate_daily_report(self, tasks, distractions):
        if not tasks: return "今天还没有记录。"
        if not self.client: return "请配置 API Key。"
        prompt = f"""
        角色:毒舌效能教练。数据:{tasks} 分心:{distractions}
        写一份200字日报，总结成就，指出问题。
        """
        try:
            res = self.client.chat.completions.create(model=CONFIG.get("model"), messages=[{"role": "user", "content": prompt}], temperature=0.7)
            return res.choices[0].message.content
        except Exception as e: return f"生成失败: {e}"