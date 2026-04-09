import json, datetime, argparse, collections, random

class WorkFlowAI:
    def __init__(self, data):
        self.data = data

    def analyze(self):
        trends = {
            "emails_per_day": collections.defaultdict(int),
            "longest_meeting_duration": datetime.timedelta(0),
            "most_visited_websites": (None, 0),
        }

        for category in self.data:
            if category == "calendar":
                for event in self.data[category]:
                    if event["start"].hour < 9 or event["start"].hour > 18:
                        print(f"Unproductive hour detected: {event['title']} at {event['start']}")
                    if event["duration"] > trends["longest_meeting_duration"].total_seconds():
                        trends["longest_meeting_duration"] = event["duration"]
            else:
                len_category = len(self.data[category])
                trends["emails_per_day"][len(self.data["calendar"])] += len_category

        print("Analyzing trends...")
        print(f"Average emails per day: {dict(trends['emails_per_day'])}")
        print(f"Longest meeting duration: {trends['longest_meeting_duration']}")
        if trends["most_visited_websites"] is None:
            most_visited = self.data["browsing_history"][0]
        else:
            most_visited = trends["most_visited_websites"][0]
        print(f"Most visited website: {most_visited}")

if __name__ == "__main__":
    data = {
        "emails": ["email1@example.com", "email2@example.com"],
        "calendar": [
            {"title": "Meeting A", "start": datetime.datetime(2023, 3, 15, 10, 30)},
            {"title": "Project X", "start": datetime.datetime(2023, 3, 16, 9, 0), "duration": 120},
        ],
        "documents": ["document1.txt", "document2.pdf"],
        "browsing_history": ["google.com", "github.com", "stackoverflow.com"],
    }

    try:
        wfa = WorkFlowAI(data)
        wfa.analyze()
    except Exception as e:
        print("Error:", str(e))