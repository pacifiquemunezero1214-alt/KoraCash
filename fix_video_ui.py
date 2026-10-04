from pathlib import Path

path = Path("templates/home.html")

content = path.read_text(encoding="utf-8")

old = """        {% if video %}

            <div class="description">
                {{ video.description }}
            </div>

            <div class="video-box">

                <a
                    href="{{ video.video_url }}"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="video-link"
                    id="videoLink"
                >
                    ▶ Open Video
                </a>

                <div class="timer" id="timerText">
                    Watch for {{ min_video_watch_seconds or 30 }} seconds
                </div>

                <div class="progress">
                    <div
                        class="progress-bar"
                        id="videoProgress">
                    </div>
                </div>

            </div>


            {% if daily_activity and daily_activity.video_completed %}

                <button class="btn btn-primary" disabled>
                    ✓ Video Reward Received
                </button>

            {% else %}

                <button
                    class="btn btn-primary"
                    id="videoRewardBtn"
                    disabled
                >
                    Complete Video
                </button>

            {% endif %}


            <div id="videoStatus" class="status"></div>

        {% else %}

            <div class="empty">
                No video available today.
            </div>

        {% endif %}"""

new = """        {% if video %}

            {% if daily_activity and daily_activity.video_completed %}

                <div class="description">
                    {{ video.description }}
                </div>

                <div class="video-box">
                    <div class="timer">
                        ✓ Today's video has been completed.
                    </div>

                    <div class="progress">
                        <div
                            class="progress-bar"
                            style="width: 100%;"
                        ></div>
                    </div>
                </div>

                <button class="btn btn-primary" disabled>
                    ✓ Video Reward Received
                </button>

                <div class="status success">
                    Come back tomorrow for a new video.
                </div>

            {% else %}

                <div class="description">
                    {{ video.description }}
                </div>

                <div class="video-box">

                    <a
                        href="{{ video.video_url }}"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="video-link"
                        id="videoLink"
                    >
                        ▶ Open Video
                    </a>

                    <div class="timer" id="timerText">
                        Watch for {{ min_video_watch_seconds or 30 }} seconds
                    </div>

                    <div class="progress">
                        <div
                            class="progress-bar"
                            id="videoProgress">
                        </div>
                    </div>

                </div>

                <button
                    class="btn btn-primary"
                    id="videoRewardBtn"
                    disabled
                >
                    Complete Video
                </button>

                <div id="videoStatus" class="status"></div>

            {% endif %}

        {% else %}

            <div class="empty">
                No video available today.
            </div>

        {% endif %}"""

if old not in content:
    print("ERROR: VIDEO BLOCK NOT FOUND")
    raise SystemExit(1)

path.write_text(
    content.replace(old, new, 1),
    encoding="utf-8"
)

print("VIDEO BLOCK UPDATED SUCCESSFULLY")