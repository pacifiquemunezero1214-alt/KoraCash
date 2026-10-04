[1mdiff --git a/app.py b/app.py[m
[1mindex 35120a2..26d536c 100644[m
[1m--- a/app.py[m
[1m+++ b/app.py[m
[36m@@ -4043,7 +4043,15 @@[m [mdef confirm_video():[m
 [m
             watch_seconds = 0[m
 [m
[31m-        if watch_seconds < MIN_VIDEO_WATCH_SECONDS:[m
[32m+[m[32m                # ----------------------------------------------------[m
[32m+[m[32m        # VIDEO DURATION VALIDATION[m
[32m+[m[32m        # ----------------------------------------------------[m
[32m+[m[32m        # Frontend izohereza igihe nyacyo video ya YouTube[m
[32m+[m[32m        # imara iyo igeze kuri 100%.[m
[32m+[m[32m        # Nta 30 seconds fixed requirement ikiriho.[m
[32m+[m[32m        # ----------------------------------------------------[m
[32m+[m
[32m+[m[32m        if watch_seconds <= 0:[m
 [m
             conn.rollback()[m
 [m
[36m@@ -4051,8 +4059,7 @@[m [mdef confirm_video():[m
                 {[m
                     "success": False,[m
                     "message": ([m
[31m-                        "Please watch the video for at least "[m
[31m-                        f"{MIN_VIDEO_WATCH_SECONDS} seconds."[m
[32m+[m[32m                        "Nyamuneka reba video kugeza igeze kuri 100%."[m
                     ),[m
                 }[m
             ), 400[m
[1mdiff --git a/templates/cash_in.html b/templates/cash_in.html[m
[1mindex 9ba85be..d72fc09 100644[m
[1m--- a/templates/cash_in.html[m
[1m+++ b/templates/cash_in.html[m
[36m@@ -1,10 +1,9 @@[m
 <!DOCTYPE html>[m
[31m-[m
 <html lang="en">[m
 <head>[m
     <meta charset="UTF-8">[m
     <meta name="viewport" content="width=device-width, initial-scale=1.0">[m
[31m-    <title>Save - KoraCash</title>[m
[32m+[m[32m    <title>Save &amp; Earn for 4 Months - KoraCash</title>[m
 [m
 <style>[m
     * {[m
[36m@@ -440,337 +439,328 @@[m
 <header class="header">[m
     <div class="header-inner">[m
 [m
[31m-```[m
[31m-    <a href="{{ url_for('home') }}" class="back">[m
[31m-        ← Home[m
[31m-    </a>[m
[31m-[m
[31m-    <h1>Save</h1>[m
[32m+[m[32m        <a href="{{ url_for('home') }}" class="back">[m
[32m+[m[32m            ← Home[m
[32m+[m[32m        </a>[m
 [m
[31m-    <p>[m
[31m-        Choose your saving plan and submit your payment proof.[m
[31m-    </p>[m
[32m+[m[32m        <h1>Save &amp; Earn for 4 Months</h1>[m
 [m
[31m-</div>[m
[31m-```[m
[32m+[m[32m        <p>[m
[32m+[m[32m            Save today and start earning for the next 4 months.[m
[32m+[m[32m        </p>[m
 [m
[32m+[m[32m    </div>[m
 </header>[m
 [m
 {% with messages = get_flashed_messages(with_categories=true) %}[m
 {% if messages %}[m
 [m
[31m-```[m
[31m-{% for category, message in messages %}[m
[32m+[m[32m    {% for category, message in messages %}[m
 [m
[31m-    <div class="flash {{ category }}">[m
[31m-        {{ message }}[m
[31m-    </div>[m
[32m+[m[32m        <div class="flash {{ category }}">[m
[32m+[m[32m            {{ message }}[m
[32m+[m[32m        </div>[m
 [m
[31m-{% endfor %}[m
[31m-```[m
[32m+[m[32m    {% endfor %}[m
 [m
 {% endif %}[m
 {% endwith %}[m
 [m
 <main class="container">[m
 [m
[31m-```[m
[31m-<div class="card">[m
[32m+[m[32m    <div class="card">[m
 [m
[31m-    <h2>Choose Your Saving Plan</h2>[m
[32m+[m[32m        <h2>Choose Your Saving Plan</h2>[m
 [m
[31m-    <p class="muted">[m
[31m-        Select the plan you want to save. Your selected plan[m
[31m-        determines the daily rewards available to your account.[m
[31m-    </p>[m
[32m+[m[32m        <p class="muted">[m
[32m+[m[32m            Select the plan you want to save. Your selected plan[m
[32m+[m[32m            determines the daily rewards available to your account.[m
[32m+[m[32m        </p>[m
 [m
[31m-    <div class="plans">[m
[32m+[m[32m        <div class="plans">[m
 [m
[31m-        <!-- PLAN 3,000 -->[m
[31m-        <div class="plan-option">[m
[32m+[m[32m            <!-- PLAN 3,000 -->[m
[32m+[m[32m            <div class="plan-option">[m
 [m
[31m-            <input[m
[31m-                type="radio"[m
[31m-                id="plan3000"[m
[31m-                name="plan_selector"[m
[31m-                value="3000"[m
[31m-            >[m
[32m+[m[32m                <input[m
[32m+[m[32m                    type="radio"[m
[32m+[m[32m                    id="plan3000"[m
[32m+[m[32m                    name="plan_selector"[m
[32m+[m[32m                    value="3000"[m
[32m+[m[32m                >[m
 [m
[31m-            <label[m
[31m-                for="plan3000"[m
[31m-                class="plan-card"[m
[31m-            >[m
[32m+[m[32m                <label[m
[32m+[m[32m                    for="plan3000"[m
[32m+[m[32m                    class="plan-card"[m
[32m+[m[32m                >[m
 [m
[31m-                <div class="plan-icon">[m
[31m-                    💰[m
[31m-                </div>[m
[32m+[m[32m                    <div class="plan-icon">[m
[32m+[m[32m                        💰[m
[32m+[m[32m                    </div>[m
 [m
[31m-                <div class="plan-name">[m
[31m-                    Plan 3,000[m
[31m-                </div>[m
[32m+[m[32m                    <div class="plan-name">[m
[32m+[m[32m                        Plan 3,000[m
[32m+[m[32m                    </div>[m
 [m
[31m-                <div class="plan-amount">[m
[31m-                    3,000 Frw[m
[31m-                </div>[m
[32m+[m[32m                    <div class="plan-amount">[m
[32m+[m[32m                        3,000 Frw[m
[32m+[m[32m                    </div>[m
 [m
[31m-                <div class="plan-info">[m
[31m-                    Save 3,000 Frw and access[m
[31m-                    your daily activities.[m
[31m-                </div>[m
[32m+[m[32m                    <div class="plan-info">[m
[32m+[m[32m                        Save 3,000 Frw and access[m
[32m+[m[32m                        your daily activities.[m
[32m+[m[32m                    </div>[m
 [m
[31m-                <div class="plan-reward">[m
[31m-                    🎬 Video: 300 Frw/day<br>[m
[31m-                    📝 Task: 300 Frw/day<br>[m
[31m-                    💵 Daily Total: 600 Frw[m
[31m-                </div>[m
[32m+[m[32m                    <div class="plan-reward">[m
[32m+[m[32m                        🎬 Video: 300 Frw/day<br>[m
[32m+[m[32m                        📝 Task: 300 Frw/day<br>[m
[32m+[m[32m                        💵 Daily Total: 600 Frw[m
[32m+[m[32m                    </div>[m
 [m
[31m-            </label>[m
[32m+[m[32m                </label>[m
 [m
[31m-        </div>[m
[32m+[m[32m            </div>[m
 [m
[31m-        <!-- PLAN 6,000 -->[m
[31m-        <div class="plan-option">[m
[32m+[m[32m            <!-- PLAN 6,000 -->[m
[32m+[m[32m            <div class="plan-option">[m
 [m
[31m-            <input[m
[31m-                type="radio"[m
[31m-                id="plan6000"[m
[31m-                name="plan_selector"[m
[31m-                value="6000"[m
[31m-            >[m
[32m+[m[32m                <input[m
[32m+[m[32m                    type="radio"[m
[32m+[m[32m                    id="plan6000"[m
[32m+[m[32m                    name="plan_selector"[m
[32m+[m[32m                    value="6000"[m
[32m+[m[32m                >[m
 [m
[31m-            <label[m
[31m-                for="plan6000"[m
[31m-                class="plan-card"[m
[31m-            >[m
[32m+[m[32m                <label[m
[32m+[m[32m                    for="plan6000"[m
[32m+[m[32m                    class="plan-card"[m
[32m+[m[32m                >[m
 [m
[31m-                <div class="plan-icon">[m
[31m-                    💎[m
[31m-                </div>[m
[32m+[m[32m                    <div class="plan-icon">[m
[32m+[m[32m                        💎[m
[32m+[m[32m                    </div>[m
 [m
[31m-                <div class="plan-name">[m
[31m-                    Plan 6,000[m
[31m-                </div>[m
[32m+[m[32m                    <div class="plan-name">[m
[32m+[m[32m                        Plan 6,000[m
[32m+[m[32m                    </div>[m
 [m
[31m-                <div class="plan-amount">[m
[31m-                    6,000 Frw[m
[31m-                </div>[m
[32m+[m[32m                    <div class="plan-amount">[m
[32m+[m[32m                        6,000 Frw[m
[32m+[m[32m                    </div>[m
 [m
[31m-                <div class="plan-info">[m
[31m-                    Save 6,000 Frw and access[m
[31m-                    your daily activities.[m
[31m-                </div>[m
[32m+[m[32m                    <div class="plan-info">[m
[32m+[m[32m                        Save 6,000 Frw and access[m
[32m+[m[32m                        your daily activities.[m
[32m+[m[32m                    </div>[m
 [m
[31m-                <div class="plan-reward">[m
[31m-                    🎬 Video: 600 Frw/day<br>[m
[31m-                    📝 Task: 600 Frw/day<br>[m
[31m-                    💵 Daily Total: 1,200 Frw[m
[31m-                </div>[m
[32m+[m[32m                    <div class="plan-reward">[m
[32m+[m[32m                        🎬 Video: 600 Frw/day<br>[m
[32m+[m[32m                        📝 Task: 600 Frw/day<br>[m
[32m+[m[32m                        💵 Daily Total: 1,200 Frw[m
[32m+[m[32m                    </div>[m
 [m
[31m-            </label>[m
[32m+[m[32m                </label>[m
[32m+[m
[32m+[m[32m            </div>[m
 [m
         </div>[m
 [m
[31m-    </div>[m
[32m+[m[32m        <div[m
[32m+[m[32m            id="selectedText"[m
[32m+[m[32m            class="selected-text"[m
[32m+[m[32m        >[m
[32m+[m[32m            Selected plan: None[m
[32m+[m[32m        </div>[m
 [m
[31m-    <div[m
[31m-        id="selectedText"[m
[31m-        class="selected-text"[m
[31m-    >[m
[31m-        Selected plan: None[m
[31m-    </div>[m
[32m+[m[32m        <div class="payment-box">[m
 [m
[31m-    <div class="payment-box">[m
[32m+[m[32m            <div class="payment-label">[m
[32m+[m[32m                Send your payment to[m
[32m+[m[32m            </div>[m
 [m
[31m-        <div class="payment-label">[m
[31m-            Send your payment to[m
[31m-        </div>[m
[32m+[m[32m            <div class="payment-number">[m
[32m+[m[32m                {{ payment_number }}[m
[32m+[m[32m            </div>[m
[32m+[m
[32m+[m[32m            <a[m
[32m+[m[32m                href="tel:{{ payment_number }}"[m
[32m+[m[32m                class="call-btn"[m
[32m+[m[32m            >[m
[32m+[m[32m                📞 Call Now[m
[32m+[m[32m            </a>[m
 [m
[31m-        <div class="payment-number">[m
[31m-            {{ payment_number }}[m
         </div>[m
 [m
[31m-        <a[m
[31m-            href="tel:{{ payment_number }}"[m
[31m-            class="call-btn"[m
[32m+[m[32m        <form[m
[32m+[m[32m            method="POST"[m
[32m+[m[32m            action="{{ url_for('cash_in') }}"[m
[32m+[m[32m            id="saveForm"[m
[32m+[m[32m            enctype="multipart/form-data"[m
         >[m
[31m-            📞 Call Now[m
[31m-        </a>[m
 [m
[31m-    </div>[m
[32m+[m[32m            <input[m
[32m+[m[32m                type="hidden"[m
[32m+[m[32m                name="amount"[m
[32m+[m[32m                id="amount"[m
[32m+[m[32m                value=""[m
[32m+[m[32m            >[m
 [m
[31m-    <form[m
[31m-        method="POST"[m
[31m-        action="{{ url_for('cash_in') }}"[m
[31m-        id="saveForm"[m
[31m-        enctype="multipart/form-data"[m
[31m-    >[m
[31m-[m
[31m-        <input[m
[31m-            type="hidden"[m
[31m-            name="amount"[m
[31m-            id="amount"[m
[31m-            value=""[m
[31m-        >[m
[32m+[m[32m            <div class="proof-section">[m
 [m
[31m-        <div class="proof-section">[m
[32m+[m[32m                <div class="proof-title">[m
[32m+[m[32m                    📸 Upload MoMo Payment Message[m
[32m+[m[32m                </div>[m
 [m
[31m-            <div class="proof-title">[m
[31m-                📸 Upload MoMo Payment Message[m
[31m-            </div>[m
[32m+[m[32m                <div class="proof-description">[m
[32m+[m[32m                    After sending the money, take a screenshot of[m
[32m+[m[32m                    your MoMo confirmation message and upload it[m
[32m+[m[32m                    here. The admin will review it before approving[m
[32m+[m[32m                    your Save request.[m
[32m+[m[32m                </div>[m
 [m
[31m-            <div class="proof-description">[m
[31m-                After sending the money, take a screenshot of[m
[31m-                your MoMo confirmation message and upload it[m
[31m-                here. The admin will review it before approving[m
[31m-                your Save request.[m
[31m-            </div>[m
[32m+[m[32m                <label[m
[32m+[m[32m                    for="paymentProof"[m
[32m+[m[32m                    class="upload-box"[m
[32m+[m[32m                >[m
 [m
[31m-            <label[m
[31m-                for="paymentProof"[m
[31m-                class="upload-box"[m
[31m-            >[m
[32m+[m[32m                    <div class="upload-icon">[m
[32m+[m[32m                        📤[m
[32m+[m[32m                    </div>[m
 [m
[31m-                <div class="upload-icon">[m
[31m-                    📤[m
[31m-                </div>[m
[32m+[m[32m                    <span class="upload-label">[m
[32m+[m[32m                        Tap to upload MoMo screenshot[m
[32m+[m[32m                    </span>[m
 [m
[31m-                <span class="upload-label">[m
[31m-                    Tap to upload MoMo screenshot[m
[31m-                </span>[m
[32m+[m[32m                    <div class="upload-hint">[m
[32m+[m[32m                        JPG, JPEG, PNG or WEBP[m
[32m+[m[32m                    </div>[m
 [m
[31m-                <div class="upload-hint">[m
[31m-                    JPG, JPEG, PNG or WEBP[m
[31m-                </div>[m
[32m+[m[32m                </label>[m
 [m
[31m-            </label>[m
[32m+[m[32m                <input[m
[32m+[m[32m                    type="file"[m
[32m+[m[32m                    name="payment_proof"[m
[32m+[m[32m                    id="paymentProof"[m
[32m+[m[32m                    accept="image/jpeg,image/png,image/webp"[m
[32m+[m[32m                    required[m
[32m+[m[32m                >[m
 [m
[31m-            <input[m
[31m-                type="file"[m
[31m-                name="payment_proof"[m
[31m-                id="paymentProof"[m
[31m-                accept="image/jpeg,image/png,image/webp"[m
[31m-                required[m
[31m-            >[m
[32m+[m[32m                <div[m
[32m+[m[32m                    id="fileName"[m
[32m+[m[32m                    class="file-name"[m
[32m+[m[32m                ></div>[m
 [m
[31m-            <div[m
[31m-                id="fileName"[m
[31m-                class="file-name"[m
[31m-            ></div>[m
[32m+[m[32m            </div>[m
 [m
[31m-        </div>[m
[32m+[m[32m            <button[m
[32m+[m[32m                type="submit"[m
[32m+[m[32m                class="save-btn"[m
[32m+[m[32m                id="saveButton"[m
[32m+[m[32m                disabled[m
[32m+[m[32m            >[m
[32m+[m[32m                Choose a Plan First[m
[32m+[m[32m            </button>[m
 [m
[31m-        <button[m
[31m-            type="submit"[m
[31m-            class="save-btn"[m
[31m-            id="saveButton"[m
[31m-            disabled[m
[31m-        >[m
[31m-            Choose a Plan First[m
[31m-        </button>[m
[32m+[m[32m        </form>[m
 [m
[31m-    </form>[m
[32m+[m[32m        <div class="notice">[m
 [m
[31m-    <div class="notice">[m
[32m+[m[32m            Your payment request will remain[m
[32m+[m[32m            <strong>Pending</strong> until an admin reviews[m
[32m+[m[32m            your payment proof and confirms the payment.[m
 [m
[31m-        Your payment request will remain[m
[31m-        <strong>Pending</strong> until an admin reviews[m
[31m-        your payment proof and confirms the payment.[m
[32m+[m[32m        </div>[m
 [m
[31m-    </div>[m
[32m+[m[32m        <div class="admin-note">[m
 [m
[31m-    <div class="admin-note">[m
[32m+[m[32m            🔐 <strong>Manual Verification:</strong>[m
[32m+[m[32m            KoraCash does not automatically approve payments.[m
[32m+[m[32m            Your uploaded MoMo screenshot will be reviewed by[m
[32m+[m[32m            an admin before your saved balance is updated.[m
 [m
[31m-        🔐 <strong>Manual Verification:</strong>[m
[31m-        KoraCash does not automatically approve payments.[m
[31m-        Your uploaded MoMo screenshot will be reviewed by[m
[31m-        an admin before your saved balance is updated.[m
[32m+[m[32m        </div>[m
 [m
     </div>[m
 [m
[31m-</div>[m
[32m+[m[32m    <div class="card">[m
 [m
[31m-<div class="card">[m
[32m+[m[32m        <h2>Cash In History</h2>[m
 [m
[31m-    <h2>Cash In History</h2>[m
[32m+[m[32m        {% if cash_ins %}[m
 [m
[31m-    {% if cash_ins %}[m
[32m+[m[32m            {% for item in cash_ins %}[m
 [m
[31m-        {% for item in cash_ins %}[m
[32m+[m[32m                <div class="history-item">[m
 [m
[31m-            <div class="history-item">[m
[32m+[m[32m                    <div>[m
 [m
[31m-                <div>[m
[32m+[m[32m                        <div class="history-amount">[m
[32m+[m[32m                            {{ "{:,}".format(item["amount"]) }} Frw[m
[32m+[m[32m                        </div>[m
 [m
[31m-                    <div class="history-amount">[m
[31m-                        {{ "{:,}".format(item["amount"]) }} Frw[m
[31m-                    </div>[m
[32m+[m[32m                        <div class="history-date">[m
[32m+[m[32m                            {{ item["created_at"][:16].replace("T", " ") }}[m
[32m+[m[32m                        </div>[m
 [m
[31m-                    <div class="history-date">[m
[31m-                        {{ item["created_at"][:16].replace("T", " ") }}[m
                     </div>[m
 [m
[31m-                </div>[m
[32m+[m[32m                    <span class="status {{ item['status'] }}">[m
[32m+[m[32m                        {{ item["status"] }}[m
[32m+[m[32m                    </span>[m
 [m
[31m-                <span class="status {{ item['status'] }}">[m
[31m-                    {{ item["status"] }}[m
[31m-                </span>[m
[31m-[m
[31m-            </div>[m
[32m+[m[32m                </div>[m
 [m
[31m-        {% endfor %}[m
[32m+[m[32m            {% endfor %}[m
 [m
[31m-    {% else %}[m
[32m+[m[32m        {% else %}[m
 [m
[31m-        <p class="muted">[m
[31m-            No Cash In transactions yet.[m
[31m-        </p>[m
[32m+[m[32m            <p class="muted">[m
[32m+[m[32m                No Cash In transactions yet.[m
[32m+[m[32m            </p>[m
 [m
[31m-    {% endif %}[m
[32m+[m[32m        {% endif %}[m
 [m
[31m-</div>[m
[31m-```[m
[32m+[m[32m    </div>[m
 [m
 </main>[m
 [m
 <nav class="bottom-nav">[m
 [m
[31m-```[m
[31m-<div class="nav-inner">[m
[31m-[m
[31m-    <a[m
[31m-        href="{{ url_for('home') }}"[m
[31m-        class="nav-item"[m
[31m-    >[m
[31m-        <span class="nav-icon">⌂</span>[m
[31m-        <span>Home</span>[m
[31m-    </a>[m
[31m-[m
[31m-    <a[m
[31m-        href="