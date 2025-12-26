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

    def create_task_profile(self, main_goal, sub_goal):
        """为当前任务创建一个详细的分析画像，包括允许的工具、关键词和可能用到的资源类别"""
        if MOCK_MODE or not self.client:
            self.current_profile = {"allowed_tools": ["python", "vscode"], "keywords": ["code"], "categories": ["programming"]}
            return
        
        prompt = f"""
        任务背景：
        总目标："{main_goal}"
        当前子任务："{sub_goal}"
        
        请为这个任务生成一个监控画像：
        - 允许的工具/应用名 (allowed_tools)
        - 相关的核心关键词 (keywords)
        - 相关的活动类别 (categories) - 比如：搜索、查阅文档、编码、设计等
        
        提示：Antigravity 是 Google 的编程工具。

        JSON格式：{{ "allowed_tools": [], "keywords": [], "categories": [] }}
        """
        try:
            res = self.client.chat.completions.create(model=CONFIG.get("model"), messages=[{"role": "user", "content": prompt}], temperature=0.2, response_format={"type": "json_object"})
            self.current_profile = json.loads(res.choices[0].message.content)
        except: 
            self.current_profile = {"allowed_tools": [], "keywords": [], "categories": []}

    def judge(self, main_goal, sub_goal, active_window, process_name):
        if not self.current_profile: return False, "加载中..."
        
        txt = (active_window + " " + process_name).lower()
        
        # 1. 快速系统白名单
        sys_white = ["explorer", "searchapp", "context menu", "新标签页", "new tab", "task switcher"]
        if any(s in txt for s in sys_white): return False, "System"
        
        # 2. 快速画像匹配 (减少不必要的LLM调用)
        for w in self.current_profile.get("allowed_tools", []) + self.current_profile.get("keywords", []):
            if w.lower() in txt: return False, f"Matched Profile: {w}"
            
        if MOCK_MODE or not self.client: return True, "[模拟] 异常"
        
        # 3. 深度AI判定
        prompt = f"""
你是一个专业的高级专注力审计员。你的目标是基于用户的具体任务上下文，判断用户的当前窗口是否真正处于工作状态。

上下文信息：
- 用户总目标: "{main_goal}"
- 当前具体子任务: "{sub_goal}"
- 允许的画像范围: {self.current_profile}
- 当前活动窗口标题: "{active_window}"
- 运行进程名: "{process_name}"

判定准则：
1. 【深层关联】：即使窗口名称不直接包含关键词，但它是否是完成该子任务所必须的支撑动作？（例如：写代码时查阅特定的API文档是正常的，但看搞笑视频不是）
2. 【动作属性】：该应用属于什么类别？（浏览器通常中立，需要看具体页面标题；音乐播放器如果是后台运行通常忽略，但如果标题是"正在播放..."且占用了焦点则可能是分心）
3. 【目标偏移】：行为是否正偏离"{sub_goal}"？如果用户宣称在"写Python代码"却在看"Java面试题"，这也是一种潜在的分心。

请以JSON格式严谨返回：
{{
  "is_distracted": bool,

  "reason": "指出具体的偏差原因（15字以内，搞怪的方式警告我们不要分心，不要过于严肃）",
  "confidence": float(0-1)
}}

"""
        try:
            res = self.client.chat.completions.create(
                model=CONFIG.get("model"), 
                messages=[{"role": "user", "content": prompt}], 
                max_tokens=100, 
                temperature=0.5,  # 降低温度以获得更一致的判断
                response_format={"type": "json_object"}
            )
            data = json.loads(res.choices[0].message.content)
            is_distracted = data.get("is_distracted", False)
            reason = data.get("reason", "注意力分散")
            return is_distracted, reason
        except Exception as e:
            # 降级处理：如果API调用失败，使用简单规则判断
            distraction_keywords = ["video", "game", "social", "shopping", "娱乐", "游戏", "视频", "购物", "社交"]
            if any(kw in txt for kw in distraction_keywords):
                return True, "疑似分心"
            return False, "Err"

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