#!/usr/bin/env python3
"""
Schedule Agent - iCloud Calendar Integration

iCloud CalDAV를 통해 일정 조회 및 등록을 담당하는 에이전트
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import caldav
from caldav.elements import dav, cdav
import pytz
from dateutil import parser as date_parser
import re
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class ScheduleAgent:
    """iCloud Calendar 연동 에이전트"""

    def __init__(self):
        """
        iCloud CalDAV 클라이언트 초기화 (Phase 1.5: 멀티 캘린더, CST 시간대)

        환경 변수:
            ICLOUD_USERNAME: Apple ID (이메일)
            ICLOUD_APP_PASSWORD: 앱 전용 암호 (appleid.apple.com에서 생성)

        Note:
            - 모든 캘린더를 자동으로 검색합니다 (Reminders 제외)
            - 시간대는 CST (America/Chicago) 기준입니다
        """
        self.username = os.getenv('ICLOUD_USERNAME')
        self.password = os.getenv('ICLOUD_APP_PASSWORD')
        self.calendar_name = os.getenv('ICLOUD_CALENDAR_NAME', 'Calendar')  # Legacy support
        
        if not self.username or not self.password:
            raise ValueError(
                "ICLOUD_USERNAME and ICLOUD_APP_PASSWORD must be set in .env file.\n"
                "Generate app-specific password at: https://appleid.apple.com"
            )
        
        # CalDAV 클라이언트 초기화
        self.caldav_url = f"https://caldav.icloud.com"
        self.client = None
        self.principal = None
        self.calendar = None

        # CST 시간대 (America/Chicago) - Phase 1.5 개편
        self.timezone = pytz.timezone('America/Chicago')

        logger.info("ScheduleAgent initialized (CST timezone)")
    
    def connect(self) -> bool:
        """
        iCloud CalDAV 서버에 연결 (Phase 1.5: 멀티 캘린더 지원)

        Returns:
            bool: 연결 성공 여부
        """
        try:
            # CalDAV 클라이언트 생성
            self.client = caldav.DAVClient(
                url=self.caldav_url,
                username=self.username,
                password=self.password
            )

            # Principal 가져오기 (사용자 정보)
            self.principal = self.client.principal()

            # 캘린더 목록 확인
            calendars = self.principal.calendars()

            if not calendars:
                logger.error("No calendars found")
                return False

            # 멀티 캘린더 연결 성공
            calendar_names = [cal.name for cal in calendars if cal.name != 'Reminders']
            logger.info(f"✅ Connected to {len(calendar_names)} calendars (excluding Reminders)")
            logger.info(f"   Calendars: {', '.join(calendar_names)}")
            return True

        except Exception as e:
            logger.error(f"CalDAV connection failed: {e}")
            return False
    
    def _escape_markdown(self, text: str) -> str:
        """
        텔레그램 마크다운 파싱 오류 방지를 위한 이스케이프 처리
        
        Args:
            text: 원본 텍스트
            
        Returns:
            str: 이스케이프 처리된 텍스트
        """
        if not text:
            return ""
        
        # 언더바를 백슬래시로 이스케이프
        text = text.replace('_', r'\_')
        
        # 기타 마크다운 특수문자 이스케이프 (필요시 추가)
        # text = text.replace('*', r'\*')
        # text = text.replace('[', r'\[')
        # text = text.replace('`', r'\`')
        
        return text
    
    def get_daily_briefing(self) -> Dict[str, List[Dict]]:
        """
        오늘과 내일의 일정 조회 (Phase 1.5: 멀티 캘린더 통합 검색, CST 기준)

        모든 캘린더를 순회하며 일정을 수집하고 시간순으로 정렬합니다.
        Reminders 캘린더는 제외됩니다.

        Returns:
            Dict: {
                'today': [일정1, 일정2, ...],
                'tomorrow': [일정1, 일정2, ...],
                'status': 'success' | 'error',
                'message': str
            }
        """
        if not self.principal:
            if not self.connect():
                return {
                    'today': [],
                    'tomorrow': [],
                    'status': 'error',
                    'message': 'CalDAV 연결 실패'
                }

        try:
            # CST 시간 기준으로 오늘/내일 범위 계산
            now = datetime.now(self.timezone)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            tomorrow_start = today_end
            tomorrow_end = tomorrow_start + timedelta(days=1)

            logger.info(f"Fetching events from {today_start} to {tomorrow_end} (CST)")

            # 모든 캘린더에서 일정 수집
            all_today_events = []
            all_tomorrow_events = []

            calendars = self.principal.calendars()
            valid_calendar_count = 0

            for cal in calendars:
                # Reminders 캘린더 제외
                if cal.name == 'Reminders':
                    logger.debug(f"Skipping calendar: {cal.name}")
                    continue

                try:
                    logger.debug(f"Searching calendar: {cal.name}")

                    # 오늘 일정 가져오기
                    today_events = cal.date_search(
                        start=today_start,
                        end=today_end,
                        expand=True
                    )
                    # 캘린더 이름과 함께 파싱
                    parsed_today = self._parse_events(today_events, calendar_name=cal.name)
                    all_today_events.extend(parsed_today)

                    # 내일 일정 가져오기
                    tomorrow_events = cal.date_search(
                        start=tomorrow_start,
                        end=tomorrow_end,
                        expand=True
                    )
                    # 캘린더 이름과 함께 파싱
                    parsed_tomorrow = self._parse_events(tomorrow_events, calendar_name=cal.name)
                    all_tomorrow_events.extend(parsed_tomorrow)

                    valid_calendar_count += 1

                except Exception as e:
                    logger.warning(f"Failed to search calendar '{cal.name}': {e}")
                    continue

            # 시간순 정렬
            all_today_events.sort(key=lambda x: x['start'])
            all_tomorrow_events.sort(key=lambda x: x['start'])

            logger.info(
                f"Retrieved {len(all_today_events)} events for today, "
                f"{len(all_tomorrow_events)} for tomorrow from {valid_calendar_count} calendars"
            )

            return {
                'today': all_today_events,
                'tomorrow': all_tomorrow_events,
                'status': 'success',
                'message': f'오늘 {len(all_today_events)}개, 내일 {len(all_tomorrow_events)}개 일정'
            }

        except Exception as e:
            logger.error(f"Failed to get daily briefing: {e}")
            return {
                'today': [],
                'tomorrow': [],
                'status': 'error',
                'message': f'일정 조회 실패: {str(e)}'
            }
    
    def _parse_events(self, events: List, calendar_name: str = "") -> List[Dict]:
        """
        CalDAV 이벤트를 파싱하여 딕셔너리 리스트로 변환

        Args:
            events: CalDAV 이벤트 리스트
            calendar_name: 캘린더 이름 (Phase 1.5: 라벨 표시용)

        Returns:
            List[Dict]: 파싱된 일정 리스트
        """
        parsed_events = []

        for event in events:
            try:
                # iCalendar 데이터 파싱
                ical = event.icalendar_component
                
                # 제목
                summary = str(ical.get('SUMMARY', '제목 없음'))
                
                # 시작/종료 시간
                dtstart = ical.get('DTSTART')
                dtend = ical.get('DTEND')
                
                # datetime 객체로 변환
                if dtstart:
                    start_dt = dtstart.dt
                    if isinstance(start_dt, datetime):
                        # 시간대가 없으면 한국 시간으로 설정
                        if start_dt.tzinfo is None:
                            start_dt = self.timezone.localize(start_dt)
                        else:
                            start_dt = start_dt.astimezone(self.timezone)
                    else:
                        # date 객체인 경우 (종일 일정)
                        start_dt = datetime.combine(start_dt, datetime.min.time())
                        start_dt = self.timezone.localize(start_dt)
                else:
                    continue  # 시작 시간 없으면 스킵
                
                if dtend:
                    end_dt = dtend.dt
                    if isinstance(end_dt, datetime):
                        if end_dt.tzinfo is None:
                            end_dt = self.timezone.localize(end_dt)
                        else:
                            end_dt = end_dt.astimezone(self.timezone)
                    else:
                        end_dt = datetime.combine(end_dt, datetime.min.time())
                        end_dt = self.timezone.localize(end_dt)
                else:
                    end_dt = start_dt + timedelta(hours=1)  # 기본 1시간
                
                # 장소
                location = str(ical.get('LOCATION', ''))
                
                # 설명
                description = str(ical.get('DESCRIPTION', ''))
                
                # 종일 일정 여부
                all_day = not isinstance(ical.get('DTSTART').dt, datetime)
                
                # 마크다운 이스케이프 처리
                summary_escaped = self._escape_markdown(summary)
                location_escaped = self._escape_markdown(location)
                description_escaped = self._escape_markdown(description)
                calendar_name_escaped = self._escape_markdown(calendar_name)

                parsed_events.append({
                    'summary': summary_escaped,
                    'start': start_dt,
                    'end': end_dt,
                    'location': location_escaped,
                    'description': description_escaped,
                    'all_day': all_day,
                    'calendar_name': calendar_name,  # 원본 캘린더 이름
                    'calendar_name_escaped': calendar_name_escaped,  # 이스케이프된 캘린더 이름
                    'raw_summary': summary,  # 원본 (이스케이프 전)
                    'raw_location': location
                })
                
            except Exception as e:
                logger.warning(f"Failed to parse event: {e}")
                continue
        
        # 시작 시간 기준 정렬
        parsed_events.sort(key=lambda x: x['start'])
        
        return parsed_events
    
    def format_daily_briefing(self, briefing: Dict) -> str:
        """
        일정 브리핑을 텔레그램 마크다운 형식으로 포맷팅 (Phase 1.5: CST 기준)

        Args:
            briefing: get_daily_briefing() 결과

        Returns:
            str: 포맷팅된 메시지 (Markdown)
        """
        if briefing['status'] == 'error':
            return f"❌ {briefing['message']}"

        today_events = briefing['today']
        tomorrow_events = briefing['tomorrow']

        # 메시지 헤더 (CST 시간 표시)
        now = datetime.now(self.timezone)
        message = f"📅 **일정 브리핑** ({now.strftime('%Y-%m-%d %H:%M')} CST)\n\n"
        
        # 오늘 일정
        message += "**📌 오늘**\n"
        if today_events:
            for idx, event in enumerate(today_events, 1):
                time_str = self._format_event_time(event)
                # 캘린더 라벨 추가
                calendar_label = f"[{event['calendar_name_escaped']}]"
                message += f"{idx}. {time_str} - {calendar_label} {event['summary']}\n"
                if event['location']:
                    message += f"   📍 {event['location']}\n"
        else:
            message += "☕ 예정된 일정이 없습니다.\n"

        message += "\n"

        # 내일 일정
        message += "**📌 내일**\n"
        if tomorrow_events:
            for idx, event in enumerate(tomorrow_events, 1):
                time_str = self._format_event_time(event)
                # 캘린더 라벨 추가
                calendar_label = f"[{event['calendar_name_escaped']}]"
                message += f"{idx}. {time_str} - {calendar_label} {event['summary']}\n"
                if event['location']:
                    message += f"   📍 {event['location']}\n"
        else:
            message += "☕ 예정된 일정이 없습니다.\n"
        
        return message
    
    def _format_event_time(self, event: Dict) -> str:
        """
        일정 시간 포맷팅 (Phase 1.5: 종일 일정 표시 개선)

        Args:
            event: 일정 딕셔너리

        Returns:
            str: 포맷팅된 시간 문자열
        """
        if event['all_day']:
            return "[종일]"
        
        start = event['start']
        end = event['end']
        
        # 같은 날인 경우
        if start.date() == end.date():
            return f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
        else:
            return f"{start.strftime('%m/%d %H:%M')}-{end.strftime('%m/%d %H:%M')}"
    
    def add_event(
        self,
        summary: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        location: str = "",
        description: str = "",
        all_day: bool = False
    ) -> Dict[str, str]:
        """
        캘린더에 새 일정 추가
        
        Args:
            summary: 일정 제목
            start_time: 시작 시간
            end_time: 종료 시간 (None이면 시작 시간 + 1시간)
            location: 장소
            description: 설명
            all_day: 종일 일정 여부
            
        Returns:
            Dict: {
                'status': 'success' | 'error',
                'message': str,
                'event_id': str (성공 시)
            }
        """
        if not self.calendar:
            if not self.connect():
                return {
                    'status': 'error',
                    'message': 'CalDAV 연결 실패'
                }
        
        try:
            # 종료 시간 기본값 설정
            if end_time is None:
                if all_day:
                    end_time = start_time + timedelta(days=1)
                else:
                    end_time = start_time + timedelta(hours=1)
            
            # 시간대 설정 (없으면 한국 시간으로)
            if start_time.tzinfo is None:
                start_time = self.timezone.localize(start_time)
            if end_time.tzinfo is None:
                end_time = self.timezone.localize(end_time)
            
            # iCalendar 형식으로 일정 생성
            ical_data = self._create_ical_event(
                summary=summary,
                start=start_time,
                end=end_time,
                location=location,
                description=description,
                all_day=all_day
            )
            
            # 캘린더에 일정 추가
            event = self.calendar.save_event(ical_data)
            
            logger.info(f"Event created: {summary} at {start_time}")
            
            return {
                'status': 'success',
                'message': f'일정 "{summary}" 등록 완료',
                'event_id': str(event.id) if hasattr(event, 'id') else 'unknown'
            }
            
        except Exception as e:
            logger.error(f"Failed to add event: {e}")
            return {
                'status': 'error',
                'message': f'일정 등록 실패: {str(e)}'
            }
    
    def _create_ical_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        location: str = "",
        description: str = "",
        all_day: bool = False
    ) -> str:
        """
        iCalendar 형식의 이벤트 데이터 생성
        
        Args:
            summary: 제목
            start: 시작 시간
            end: 종료 시간
            location: 장소
            description: 설명
            all_day: 종일 일정 여부
            
        Returns:
            str: iCalendar 형식 문자열
        """
        # 타임스탬프
        now = datetime.now(pytz.UTC)
        dtstamp = now.strftime('%Y%m%dT%H%M%SZ')
        
        # 종일 일정은 날짜만
        if all_day:
            dtstart = start.strftime('%Y%m%d')
            dtend = end.strftime('%Y%m%d')
            dtstart_line = f"DTSTART;VALUE=DATE:{dtstart}"
            dtend_line = f"DTEND;VALUE=DATE:{dtend}"
        else:
            # UTC로 변환
            start_utc = start.astimezone(pytz.UTC)
            end_utc = end.astimezone(pytz.UTC)
            dtstart = start_utc.strftime('%Y%m%dT%H%M%SZ')
            dtend = end_utc.strftime('%Y%m%dT%H%M%SZ')
            dtstart_line = f"DTSTART:{dtstart}"
            dtend_line = f"DTEND:{dtend}"
        
        # iCalendar 데이터
        ical = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Polaris Agent//Schedule Agent//EN
BEGIN:VEVENT
UID:{now.timestamp()}@polaris
DTSTAMP:{dtstamp}
{dtstart_line}
{dtend_line}
SUMMARY:{summary}"""
        
        if location:
            ical += f"\nLOCATION:{location}"
        
        if description:
            ical += f"\nDESCRIPTION:{description}"
        
        ical += "\nEND:VEVENT\nEND:VCALENDAR"
        
        return ical
    
    def parse_natural_time(self, text: str) -> Optional[datetime]:
        """
        자연어 시간 표현을 datetime 객체로 파싱
        
        Args:
            text: 자연어 시간 표현 (예: "오늘 오후 3시", "내일 10:00", "2024-02-07 15:00")
            
        Returns:
            Optional[datetime]: 파싱된 datetime 객체 (실패 시 None)
        """
        try:
            # 한국 시간 기준
            now = datetime.now(self.timezone)
            
            # "오늘", "내일" 같은 표현 처리
            text = text.strip()
            base_date = now
            
            if '오늘' in text:
                base_date = now
                text = text.replace('오늘', '').strip()
            elif '내일' in text:
                base_date = now + timedelta(days=1)
                text = text.replace('내일', '').strip()
            elif '모레' in text:
                base_date = now + timedelta(days=2)
                text = text.replace('모레', '').strip()
            
            # "오후", "오전" 처리
            is_pm = '오후' in text or 'PM' in text.upper()
            is_am = '오전' in text or 'AM' in text.upper()
            text = text.replace('오후', '').replace('오전', '').replace('PM', '').replace('AM', '').strip()
            
            # dateutil로 파싱 시도
            try:
                parsed = date_parser.parse(text, default=base_date)
                
                # 오전/오후 처리
                if is_pm and parsed.hour < 12:
                    parsed = parsed.replace(hour=parsed.hour + 12)
                elif is_am and parsed.hour >= 12:
                    parsed = parsed.replace(hour=parsed.hour - 12)
                
                # 시간대 설정
                if parsed.tzinfo is None:
                    parsed = self.timezone.localize(parsed)
                
                return parsed
                
            except Exception:
                # 실패 시 None 반환
                return None
                
        except Exception as e:
            logger.warning(f"Failed to parse natural time '{text}': {e}")
            return None
    
    def add_event_from_text(self, text: str) -> Dict[str, str]:
        """
        자연어 텍스트로부터 일정 추가
        
        텍스트 형식 예시:
        - "회의 내일 오후 3시"
        - "점심약속 2024-02-07 12:00 강남역"
        - "발표 준비 오늘 14:00-16:00 연구실"
        
        Args:
            text: 자연어 텍스트
            
        Returns:
            Dict: add_event() 결과
        """
        try:
            # 간단한 파싱 로직 (개선 가능)
            parts = text.split()
            
            if len(parts) < 2:
                return {
                    'status': 'error',
                    'message': '일정 형식이 올바르지 않습니다. 예: "회의 내일 오후 3시"'
                }
            
            # 제목은 첫 단어
            summary = parts[0]
            
            # 나머지는 시간 정보로 간주
            time_text = ' '.join(parts[1:])
            
            # 시간 파싱
            start_time = self.parse_natural_time(time_text)
            
            if start_time is None:
                return {
                    'status': 'error',
                    'message': f'시간을 파싱할 수 없습니다: "{time_text}"'
                }
            
            # 장소 추출 (간단한 휴리스틱)
            location = ""
            for part in parts[2:]:
                if any(keyword in part for keyword in ['역', '빌딩', '카페', '식당', '연구실', '사무실']):
                    location = part
                    break
            
            # 일정 추가
            return self.add_event(
                summary=summary,
                start_time=start_time,
                location=location
            )
            
        except Exception as e:
            logger.error(f"Failed to add event from text: {e}")
            return {
                'status': 'error',
                'message': f'일정 추가 실패: {str(e)}'
            }


# 테스트 코드
if __name__ == "__main__":
    # ScheduleAgent 초기화
    agent = ScheduleAgent()
    
    # 연결 테스트
    if agent.connect():
        print("✅ iCloud Calendar 연결 성공")
        
        calendars = agent.principal.calendars()
        print("\n 발견된 캘린더 목록:")
        for cal in calendars:
            print(f"- {cal.name}")
        # 일정 조회 테스트
        #briefing = agent.get_daily_briefing()
        #print("\n" + agent.format_daily_briefing(briefing))
        
        # 일정 추가 테스트 (주석 처리)
        # result = agent.add_event(
        #     summary="테스트 회의",
        #     start_time=datetime.now(agent.timezone) + timedelta(hours=1),
        #     location="연구실"
        # )
        # print(f"\n{result['message']}")
    else:
        print("❌ iCloud Calendar 연결 실패")
