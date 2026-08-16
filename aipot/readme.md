<img width="1254" height="1254" alt="image" src="https://github.com/user-attachments/assets/4c1eb220-6406-47c0-b030-776552a42e44" />


# I Tried Building an AI-Powered SSH Honeypot, inspired by the DECEIVE honeypot project from those extraordinary guys at Splunk. It Failed Miserably. I don't have their talent :D

Inspired by Splunk's **DECEIVE** project, I built a proof of concept that uses DeepSeek to simulate a Linux system over SSH.

The idea is to use AI to generate realistic responses dynamically, without needing a fake filesystem. In reality, attackers would spot it within seconds.

## Why It Failed—and What I Learned

### ❌ 1. Speed Is a Dead Giveaway
Real SSH sessions typically respond in under 100 milliseconds.
My honeypot took between **2 and 30 seconds** to execute each command. The entire response then appeared at once, with no typing effect or streaming output.
An attacker enters:

```bash
ls -la
```

Then waits 15 seconds for a directory listing.

---

### ❌ 2. No Consistency Between Commands
The same command produced different results:
```text
First "ls"  → Desktop Documents Downloads
Second "ls" → Music Pictures Videos
```


---

### ❌ 3. Session Context Doesn't Exist
Consider this scenario:
```console
$ ls
Documents  Downloads  Projects

$ cd Projects
bash: cd: Projects: No such file or directory
```

But the `Projects` directory was just listed.


---

### ❌ 4. Bash Shortcuts Don't Work

The simulated shell had:

- No up arrow to recall previous commands
- No tab completion
- No `Ctrl+C` to cancel a command


---

### ❌ 5. It Is Fragile Under Load

As soon as multiple commands arrived in quick succession:
- The AI started hallucinating
- Responses became nonsensical
- Sometimes it simply stopped responding


---
## Traditional Honeypots Are More Convincing IMHO
Traditional honeypots provide:

- ✅ Instant responses
- ✅ Consistent state
- ✅ Real filesystem simulation
- ✅ Proper shell behavior


## Conclusion

**Would I deploy this?** Absolutely not.
**Do I regret building it?** No.
