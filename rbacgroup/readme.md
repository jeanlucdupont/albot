<img width="706" height="670" alt="image" src="https://github.com/user-attachments/assets/e3d858e8-dc55-4299-ab53-b730c6a08ac2" />

Let’s be honest: nobody’s AD or Entra ID group structure is perfectly clean. Groups accumulate. People change jobs. Applications come and go. Exceptions become permanent. Eventually, the organization has something that vaguely resembles RBAC—but nobody can clearly see it.

I wanted to see whether the roles were already hiding inside the existing group memberships.So I wrote a script. (Well, AI wrote a good part of it, TBH).

It uses:
- Jaccard similarity to identify users with comparable group memberships
- User clustering to turn similar-user pairs into candidate populations
- FP-Growth to find groups that frequently occur together
- Support, confidence, and lift to measure how meaningful those relationships are

And roles started appearing. That was not entirely surprising, but watching the patterns emerge from years of accumulated group memberships was still a little magical, NGL.

These are not automatically approved roles. They are candidate roles—starting points for review by application owners, managers, IAM teams, and security. Correlation can reveal an access pattern. It cannot tell you whether that access is legitimate.

**rbacgroup.py** 

Connects to Microsoft Graph, analyzes AD-synchronized and Entra ID groups, and generates an Excel workbook containing:
- Group inventory, membership, ownership, and nesting
- Identical and near-duplicate groups
- Group containment relationships
- Ownerless, empty, and lifecycle-review candidates
- Direct privileged-role assignments
- Dimilar users based on Jaccard similarity
- Candidate user clusters
- Candidate role groups and their prevalence
- Frequent group bundles found with FP-Growth
- Association rules with support, confidence, and lift
- Users who match a pattern but are missing the predicted group

The generated XLSX goes fairly deep—and on a large tenant, the analysis can take some time.

<img width="687" height="666" alt="image" src="https://github.com/user-attachments/assets/e2bbd79a-30cb-408e-bf4d-8dbbc2b43ec1" />

**rbacgroupvisualizer.py**
But having a visualization is a good complement. That's why there's a companion script that does just this.
The companion script reads the generated  XLSX and generates:
- An RBAC overview
- One user-to-group heatmap per candidate cluster

<img width="1120" height="595" alt="image" src="https://github.com/user-attachments/assets/1b89c392-93d9-48ae-857d-44908518ff9e" />


<img width="938" height="455" alt="image" src="https://github.com/user-attachments/assets/668aa524-f618-473e-adba-413cbbfefc3d" />

**Important limitations**

This is a discovery and review tool—not an automated provisioning system.
- Similar access does not prove that users perform the same job
- A common entitlement may represent widespread privilege creep
- A missing group may be intentional
- A high-confidence rule does not prove that its predicted access is appropriate
- Created and renewed dates are lifecycle metadata, not evidence of actual use
- Direct Entra directory-role assignments are reported, but nested groups are not assumed to inherit those roles
- Application owners and business managers must validate candidate roles and exceptions


