import os
import openai
from dotenv import load_dotenv

load_dotenv()

class AIProcessor:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        openai.api_key = self.api_key
    
    def process_task_description(self, description: str) -> str:
        if not description:
            return "Описание задачи отсутствует"
        
        try:
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Ты - помощник, который кратко и четко объясняет суть заказа с FL.ru. Выдели главное из описания заказа без лишних деталей."},
                    {"role": "user", "content": f"Вот описание заказа с FL.ru: \n\n{description}\n\nКратко опиши суть этого заказа в 1-3 предложениях, выделив только главное."}
                ],
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Ошибка при обработке задачи в OpenAI: {e}")
            return f"Не удалось обработать описание задачи: {str(e)}"