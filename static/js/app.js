"use strict";

/*
    KoraCash Global JavaScript
*/


/* --------------------------------------------------
   DOM READY
-------------------------------------------------- */

document.addEventListener("DOMContentLoaded", function () {

    addPageAnimation();

    preventDoubleSubmit();

    autoHideFlashMessages();

});


/* --------------------------------------------------
   PAGE ANIMATION
-------------------------------------------------- */

function addPageAnimation() {

    const elements =
        document.querySelectorAll(
            ".card, .notification, .faq, .balance-box"
        );

    elements.forEach(function (element, index) {

        element.style.animationDelay =
            Math.min(index * 40, 300) + "ms";

        element.classList.add("fade-up");

    });

}


/* --------------------------------------------------
   PREVENT DOUBLE FORM SUBMISSION
-------------------------------------------------- */

function preventDoubleSubmit() {

    const forms =
        document.querySelectorAll("form");

    forms.forEach(function (form) {

        form.addEventListener("submit", function () {

            const button =
                form.querySelector(
                    'button[type="submit"]'
                );

            if (!button) {
                return;
            }

            if (button.dataset.submitted === "true") {
                return;
            }

            button.dataset.submitted = "true";

            button.disabled = true;

            const originalText =
                button.innerHTML;

            button.dataset.originalText =
                originalText;

            button.innerHTML =
                "Please wait...";

        });

    });

}


/* --------------------------------------------------
   FLASH MESSAGE AUTO HIDE
-------------------------------------------------- */

function autoHideFlashMessages() {

    const messages =
        document.querySelectorAll(".flash");

    messages.forEach(function (message) {

        setTimeout(function () {

            message.style.transition =
                "opacity .4s ease, transform .4s ease";

            message.style.opacity = "0";

            message.style.transform =
                "translateY(-5px)";

            setTimeout(function () {

                message.remove();

            }, 450);

        }, 5000);

    });

}


/* --------------------------------------------------
   COPY TEXT
-------------------------------------------------- */

async function copyText(text) {

    try {

        await navigator.clipboard.writeText(text);

        showToast("Copied successfully!");

        return true;

    } catch (error) {

        const textarea =
            document.createElement("textarea");

        textarea.value = text;

        textarea.style.position = "fixed";
        textarea.style.opacity = "0";

        document.body.appendChild(textarea);

        textarea.select();

        try {

            document.execCommand("copy");

            showToast("Copied successfully!");

            textarea.remove();

            return true;

        } catch (copyError) {

            textarea.remove();

            showToast("Copy failed.");

            return false;

        }

    }

}


/* --------------------------------------------------
   TOAST
-------------------------------------------------- */

function showToast(message) {

    const oldToast =
        document.querySelector(".koracash-toast");

    if (oldToast) {
        oldToast.remove();
    }

    const toast =
        document.createElement("div");

    toast.className =
        "koracash-toast";

    toast.textContent =
        message;

    toast.style.position =
        "fixed";

    toast.style.left =
        "50%";

    toast.style.bottom =
        "90px";

    toast.style.transform =
        "translateX(-50%)";

    toast.style.background =
        "#17202a";

    toast.style.color =
        "white";

    toast.style.padding =
        "12px 18px";

    toast.style.borderRadius =
        "12px";

    toast.style.fontSize =
        "13px";

    toast.style.fontWeight =
        "700";

    toast.style.zIndex =
        "9999";

    toast.style.boxShadow =
        "0 8px 25px rgba(0,0,0,.18)";

    document.body.appendChild(toast);

    setTimeout(function () {

        toast.style.transition =
            "opacity .3s ease";

        toast.style.opacity =
            "0";

        setTimeout(function () {

            toast.remove();

        }, 300);

    }, 2500);

}


/* --------------------------------------------------
   CONFIRM ACTION
-------------------------------------------------- */

function confirmAction(message) {

    return window.confirm(
        message ||
        "Are you sure you want to continue?"
    );

}


/* --------------------------------------------------
   PHONE VALIDATION
-------------------------------------------------- */

function isValidRwandaPhone(phone) {

    const cleaned =
        String(phone)
            .replace(/\s+/g, "")
            .replace(/-/g, "");

    return /^(07\d{8}|\+2507\d{8}|2507\d{8})$/
        .test(cleaned);

}


/* --------------------------------------------------
   MONEY FORMAT
-------------------------------------------------- */

function formatMoney(amount) {

    const number =
        Number(amount || 0);

    return number.toLocaleString(
        "en-US",
        {
            maximumFractionDigits: 0
        }
    ) + " Frw";

}


/* --------------------------------------------------
   API HELPER
-------------------------------------------------- */

async function apiRequest(
    url,
    options = {}
) {

    const response =
        await fetch(
            url,
            {
                credentials: "same-origin",
                ...options
            }
        );

    let data = null;

    try {

        data =
            await response.json();

    } catch (error) {

        data = null;

    }

    if (!response.ok) {

        throw new Error(
            data?.message ||
            "Something went wrong."
        );

    }

    return data;

}


/* --------------------------------------------------
   NOTIFICATION COUNT
-------------------------------------------------- */

async function updateNotificationCount() {

    try {

        const response =
            await fetch(
                "/api/notifications",
                {
                    credentials:
                        "same-origin"
                }
            );

        if (!response.ok) {
            return;
        }

        const data =
            await response.json();

        const count =
            data.unread_count ??
            data.count ??
            0;

        const badges =
            document.querySelectorAll(
                ".notification-badge"
            );

        badges.forEach(function (badge) {

            if (count > 0) {

                badge.textContent =
                    count > 99
                        ? "99+"
                        : count;

                badge.style.display =
                    "flex";

            } else {

                badge.style.display =
                    "none";

            }

        });

    } catch (error) {

        /*
            Notification count is optional.
            Do not interrupt the page if
            the API is unavailable.
        */

    }

}


/* --------------------------------------------------
   RUN NOTIFICATION CHECK
-------------------------------------------------- */

document.addEventListener(
    "DOMContentLoaded",
    function () {

        updateNotificationCount();

    }
);