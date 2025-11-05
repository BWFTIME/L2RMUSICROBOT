async def start(self):
    LOGGER(__name__).info("Attempting to connect to Telegram...")
    
    while True:  # FloodWait के लिए अनंत लूप
        try:
            # super().start() ही लॉगिन का प्रयास करता है
            await super().start()
            break  # अगर login सफल होता है, तो loop से बाहर निकलें

        except errors.FloodWait as e:
            # FloodWait को हैंडल करें और रुकें
            wait_time = e.value
            LOGGER(__name__).warning(
                f"⚠️ Telegram FloodWait during login. Waiting for {wait_time} seconds before retrying..."
            )
            await asyncio.sleep(wait_time)

        except Exception as ex:
            # Login के दौरान किसी अन्य गंभीर त्रुटि को हैंडल करें और बाहर निकलें
            LOGGER(__name__).error(
                f"Bot failed to start due to a non-FloodWait error: {type(ex).__name__} - {ex}"
            )
            exit()

    # --- लॉगिन सफल होने के बाद का कोड यहाँ से शुरू होता है ---
    
    # Bot info सेट करें
    self.id = self.me.id
    self.name = self.me.first_name + " " + (self.me.last_name or "")
    self.username = self.me.username
    self.mention = self.me.mention

    # Logger ID checks (पहले की तरह)
    try:
        # ... बाकी का LOGGER_ID चेक कोड ...

    except (errors.ChannelInvalid, errors.PeerIdInvalid):
        # ... हैंडलिंग ...
        exit()
    except Exception as ex:
        # ... हैंडलिंग ...
        exit()

    # ... Admin check ...
