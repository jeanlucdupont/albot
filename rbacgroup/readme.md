**You have RBAC. You just couldn’t see it.**

<img width="706" height="670" alt="image" src="https://github.com/user-attachments/assets/e3d858e8-dc55-4299-ab53-b730c6a08ac2" />

I looked at our AD and Entra ID group memberships and tried to find the patterns hidden. Let’s be honest, now one is super clean on those.
I wrote a script (Well, AI did most of it TBH) that used Jaccard similarity to find users with similar access, then FP-Growth to identify groups that regularly go together.
And roles started appearing. Not surprised but seeing the script showing it to me was a bit magical, NGL.
Those are not perfect roles and some should not be automatically approved roles but the script found some pretty convincing candidates.

The script generates and XLSX file goes rather deep. And it will take some time!

<img width="687" height="666" alt="image" src="https://github.com/user-attachments/assets/e2bbd79a-30cb-408e-bf4d-8dbbc2b43ec1" />

But having a visualization is a good complement. That's why there's a companion script that does just this.

<img width="1120" height="595" alt="image" src="https://github.com/user-attachments/assets/1b89c392-93d9-48ae-857d-44908518ff9e" />

<img width="938" height="455" alt="image" src="https://github.com/user-attachments/assets/668aa524-f618-473e-adba-413cbbfefc3d" />


