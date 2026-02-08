-- read_mail.scpt (v3)
-- UIC 메일 계정에서 읽지 않은 메일 읽기
-- 개선: 한글/영어 받은편지함 모두 지원, 특수문자 안전 처리
-- 사용법: osascript read_mail.scpt <account_keyword> <limit>

on run argv
    -- 파라미터 받기
    set searchKeyword to item 1 of argv -- 예: "UIC"
    set mailLimit to item 2 of argv as integer -- 예: 5

    tell application "Mail"
        set outputList to {}
        set mailCount to 0
        set accountFound to false

        try
            -- 모든 계정 순회
            repeat with acc in accounts
                set accountName to name of acc

                -- 계정 이름 매칭 (대소문자 구분 없이)
                -- do shell script 대신 AppleScript 네이티브 비교 사용
                if my textContains(accountName, searchKeyword) then
                    set accountFound to true

                    -- 받은편지함 찾기 (한글/영어 모두 지원)
                    set inboxMailbox to missing value
                    set inboxNames to {"받은 편지함", "INBOX", "Inbox", "inbox"}

                    repeat with boxName in inboxNames
                        try
                            set inboxMailbox to mailbox boxName of acc
                            exit repeat
                        on error
                            -- 다음 이름 시도
                        end try
                    end repeat

                    -- 받은편지함을 못 찾으면 다음 계정으로
                    if inboxMailbox is missing value then
                        -- 계정을 찾았지만 받은편지함이 없음
                        set accountFound to false
                    else
                        -- 읽지 않은 메일만 가져오기
                        set unreadMessages to (every message of inboxMailbox whose read status is false)

                        -- 최신 메일부터 (역순)
                        repeat with i from (count of unreadMessages) to 1 by -1
                            if mailCount >= mailLimit then
                                exit repeat
                            end if

                            set msg to item i of unreadMessages

                            -- 메일 정보 추출
                            set msgSubject to my safeGetText(subject of msg)
                            set msgSender to my safeGetText(sender of msg)
                            set msgContent to my safeGetText(content of msg)
                            set msgDate to date received of msg as string

                            -- 본문 길이 제한 (500자)
                            if length of msgContent > 500 then
                                set msgContent to text 1 thru 500 of msgContent & "..."
                            end if

                            -- 특수문자 처리 (구분자 충돌 방지)
                            set msgSubject to my replaceText(msgSubject, "|||", " ")
                            set msgSender to my replaceText(msgSender, "|||", " ")
                            set msgContent to my replaceText(msgContent, "|||", " ")
                            set msgSubject to my replaceText(msgSubject, ":::", " ")
                            set msgSender to my replaceText(msgSender, ":::", " ")
                            set msgContent to my replaceText(msgContent, ":::", " ")

                            -- JSON 형식으로 구분자 사용
                            -- 형식: subject|||sender|||content|||date|||account
                            set mailInfo to msgSubject & "|||" & msgSender & "|||" & msgContent & "|||" & msgDate & "|||" & accountName
                            set end of outputList to mailInfo

                            set mailCount to mailCount + 1
                        end repeat

                        -- 계정을 찾았으면 종료 (단일 계정만 검색)
                        exit repeat
                    end if
                end if
            end repeat

            -- 결과 반환
            if not accountFound then
                return "ERROR: 계정을 찾을 수 없습니다. 사용 가능한 계정: " & my getAccountNames()
            else if mailCount > 0 then
                set AppleScript's text item delimiters to ":::"
                return outputList as text
            else
                return "NO_UNREAD_MAILS"
            end if

        on error errMsg
            return "ERROR: " & errMsg
        end try
    end tell
end run

-- 안전한 텍스트 가져오기 (null 방지)
on safeGetText(textValue)
    try
        if textValue is missing value or textValue is "" then
            return ""
        else
            return textValue as text
        end if
    on error
        return ""
    end try
end safeGetText

-- 대소문자 구분 없는 포함 체크 (do shell script 없이)
on textContains(sourceText, searchText)
    try
        set sourceTextLower to my toLowerCase(sourceText)
        set searchTextLower to my toLowerCase(searchText)
        return sourceTextLower contains searchTextLower
    on error
        return false
    end try
end textContains

-- 소문자 변환 (AppleScript 네이티브)
on toLowerCase(inputText)
    set lowerChars to "abcdefghijklmnopqrstuvwxyz"
    set upperChars to "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    set outputText to ""

    repeat with i from 1 to length of inputText
        set currentChar to character i of inputText
        set charIndex to offset of currentChar in upperChars

        if charIndex > 0 then
            set outputText to outputText & character charIndex of lowerChars
        else
            set outputText to outputText & currentChar
        end if
    end repeat

    return outputText
end toLowerCase

-- 텍스트 치환 함수
on replaceText(theText, searchString, replacementString)
    try
        set AppleScript's text item delimiters to searchString
        set theTextItems to every text item of theText
        set AppleScript's text item delimiters to replacementString
        set theText to theTextItems as string
        set AppleScript's text item delimiters to ""
        return theText
    on error
        return theText
    end try
end replaceText

-- 사용 가능한 계정 이름 가져오기
on getAccountNames()
    tell application "Mail"
        set accountNames to {}
        repeat with acc in accounts
            set end of accountNames to name of acc
        end repeat
        set AppleScript's text item delimiters to ", "
        set result to accountNames as text
        set AppleScript's text item delimiters to ""
        return result
    end tell
end getAccountNames
