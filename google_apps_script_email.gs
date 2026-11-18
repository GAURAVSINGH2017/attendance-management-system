function doPost(e) {
  try {
    const data = JSON.parse((e.postData && e.postData.contents) || "{}");
    const expectedToken = PropertiesService.getScriptProperties().getProperty("ATTENDEASE_TOKEN");
    if (!expectedToken || data.token !== expectedToken) {
      return jsonResponse({ ok: false, error: "Unauthorized request" });
    }

    const to = String(data.to || "").trim();
    const subject = String(data.subject || "").trim();
    const body = String(data.body || "").trim();
    if (!to || !subject || !body || to.length > 254 || subject.length > 200 || body.length > 5000) {
      return jsonResponse({ ok: false, error: "Missing or invalid email fields" });
    }
    if (MailApp.getRemainingDailyQuota() < 1) {
      return jsonResponse({ ok: false, error: "Daily email quota reached" });
    }

    MailApp.sendEmail({ to: to, subject: subject, body: body, name: "AttendEase" });
    return jsonResponse({ ok: true });
  } catch (error) {
    return jsonResponse({ ok: false, error: String(error).slice(0, 200) });
  }
}

function jsonResponse(data) {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
