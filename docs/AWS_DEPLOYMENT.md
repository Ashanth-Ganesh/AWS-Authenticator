# Deploy the assignment to AWS EC2

This guide uses **Ubuntu Server 24.04 LTS + Apache + Python 3 mod_wsgi + Flask + SQLite**, as requested by the assignment. React is built on your computer; Node.js is not needed on EC2. The Flask application serves both the compiled UI and `/api` from one URL.

These steps follow [AWS’s EC2 getting-started guide](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html) and [Flask’s Apache/mod_wsgi deployment documentation](https://flask.palletsprojects.com/en/stable/deploying/mod_wsgi/). The virtual environment is created using Ubuntu’s `/usr/bin/python3` because [mod_wsgi requires the same Python installation it was compiled against](https://modwsgi.readthedocs.io/en/develop/user-guides/virtual-environments.html).

## 1. Build the deployment package on Windows

In this project’s PowerShell terminal:

```powershell
npm ci
npm run build
py -3 tools/package_deploy.py
```

You should now have **dist/aws-authenticator.zip**. The package contains the compiled React UI, Flask code, database schema, and installer. It excludes your `.env`, `.venv`, database, SSH keys, and `node_modules`.

## 2. Launch an EC2 instance

1. Sign in to the [AWS Management Console](https://console.aws.amazon.com/ec2/) and select a region, such as **US East (Ohio), us-east-2**. Keep that same region selected during setup.
2. Open **EC2 → Instances → Launch instances**. Name it `aws-authenticator`.
3. Under **Application and OS Images**, select **Ubuntu**, then **Ubuntu Server 24.04 LTS (HVM), SSD Volume Type**, **64-bit (x86)**. Choose the official Canonical image.
4. Choose a small instance such as **t3.micro**, or an eligible equivalent shown for your account. Check the console’s current cost estimate and your Billing/Free Tier balance. AWS Free Tier benefits depend on your account’s plan and creation date; [AWS changed the program for new accounts in July 2025](https://aws.amazon.com/blogs/aws/aws-free-tier-update-new-customers-can-get-started-and-explore-aws-with-up-to-200-in-credits/).
5. Under **Key pair**, click **Create new key pair**. Name it `aws-authenticator-key`, select **RSA** and **.pem**, and download it. Keep it outside the project, for example in your Downloads folder. This private key is your SSH login credential; do not upload it to GitHub or include its contents in screenshots.
6. Under **Network settings → Edit**:
   - Use the default VPC and a public subnet. If your account has no default VPC, use **VPC → Your VPCs → Actions → Create default VPC**, or select an existing public subnet with a route to an internet gateway.
   - Set **Auto-assign public IP → Enable**.
   - Create a security group named `aws-authenticator-sg` with the rules below.
7. Keep a small root EBS volume, for example **8 GiB gp3**, with **Delete on termination** selected.
8. Click **Launch instance**. Wait until it is **Running** and its status checks pass. Select it and copy its **Public IPv4 DNS**. If no public DNS is shown, use its **Public IPv4 address**.

Security-group inbound rules:

| Type | Protocol / port | Source | Purpose |
| --- | --- | --- | --- |
| SSH | TCP 22 | My IP (your current public IP /32) | Your terminal connects to EC2 |
| HTTP | TCP 80 | Anywhere-IPv4, `0.0.0.0/0` | Instructor can open the webpage |
| HTTPS | TCP 443 | Anywhere-IPv4, `0.0.0.0/0` | Only needed when you configure HTTPS |

Keep the default outbound rule for package downloads. You do not need inbound ports 5000, 5173, or a database port. SQLite is a file on the server. [AWS’s security-group documentation](https://docs.aws.amazon.com/vpc/latest/userguide/security-group-rules.html) explains source addresses and inbound/outbound rules.

**Screenshots:** AMI selection, instance type, key-pair selection, network settings and inbound rules, storage, and the running instance showing its public DNS. Screenshot the key-pair selection without exposing the private key.

## 3. Connect and upload from Windows PowerShell

In your project directory, replace the example hostname below with the actual public DNS copied from your instance:

```powershell
$ec2Host = 'ec2-REPLACE-WITH-YOUR-PUBLIC-DNS.us-east-2.compute.amazonaws.com'
$keyPath = Join-Path $env:USERPROFILE 'Downloads\aws-authenticator-key.pem'
ssh -i "$keyPath" "ubuntu@$ec2Host"
```

Accept the host fingerprint on your first connection after checking that you used your instance’s address. The Ubuntu AMI’s login user is **ubuntu**. For background, see [AWS’s SSH connection guide](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/connect-linux-inst-ssh.html).

At the Ubuntu prompt, create the upload folder, then return to your local terminal:

```bash
mkdir -p /home/ubuntu/aws-authenticator
exit
```

Back in PowerShell, upload and reconnect:

```powershell
scp -i "$keyPath" .\dist\aws-authenticator.zip "ubuntu@${ec2Host}:/home/ubuntu/aws-authenticator.zip"
ssh -i "$keyPath" "ubuntu@$ec2Host"
```

If SSH reports that your key permissions are too open, restrict that file’s ACL to your Windows account using the file’s **Properties → Security → Advanced**, disabling inheritance and removing access for other users. Retry SSH. If it times out, check the instance’s public address and that the SSH rule’s **My IP** still matches your current network. You can also follow AWS’s connection troubleshooting from the linked SSH guide.

## 4. Install Apache, Flask, and SQLite on EC2

The following commands run **inside the Ubuntu SSH session**:

```bash
sudo apt-get update
sudo apt-get install -y unzip
unzip -o /home/ubuntu/aws-authenticator.zip -d /home/ubuntu/aws-authenticator
cd /home/ubuntu/aws-authenticator
sudo bash deploy/install.sh
```

The installer is for a dedicated assignment instance. It installs `apache2`, `libapache2-mod-wsgi-py3`, `python3-pip`, `python3-venv`, and `sqlite3`. It then:

- Copies application code to `/var/www/aws-authenticator`.
- Creates a virtual environment with Ubuntu’s system Python and installs Flask there. This avoids Ubuntu’s restriction on installing pip packages into the system Python environment.
- Creates a persistent session secret in `/etc/aws-authenticator.env` readable only by root and Apache’s group.
- Initializes `/var/lib/aws-authenticator/users.db` as `www-data`, so Apache can read/write the SQLite database and its journal files.
- Enables the provided Apache WSGI site on port 80, disables the default welcome page, checks Apache configuration, and restarts Apache.

The application automatically creates the tables. Do not create a separate database by hand: it would not be the database used by the website. Passwords are stored in `password_hash`, improving on the assignment’s illustrative plaintext-password example. Uploaded files are BLOBs in the `uploads` table, linked to their owner.

Verify the setup:

```bash
python3 --version
/var/www/aws-authenticator/.venv/bin/python -m pip show Flask
sqlite3 --version
sudo apache2ctl -M | grep wsgi
sudo apache2ctl configtest
systemctl is-active apache2
curl http://127.0.0.1/api/health
sudo sqlite3 /var/lib/aws-authenticator/users.db '.schema'
```

Expected results include `wsgi_module`, `Syntax OK`, `active`, `{"status":"ok"}`, and the `users` and `uploads` table definitions.

**Screenshots:** package-install output, Python/pip/Flask versions, Apache mod_wsgi/configuration checks, the health response, and the SQLite schema. Do not show the contents of `/etc/aws-authenticator.env`.

## 5. Open the page and demonstrate every requirement

In your browser, visit **http://YOUR_EC2_PUBLIC_DNS**. Enter `http://` explicitly: this setup starts with HTTP, matching the example URL in the assignment. Use sample personal information and a unique demonstration password. HTTP does not encrypt credentials; configure HTTPS before using real credentials.

1. Register a new username and password, and fill in first name, last name, email, and address.
2. Select your course’s actual **Limerick (1).txt** using the text-file input before clicking **Create account**. The file is not bundled because it was not provided in the repository.
3. Confirm the browser opens **/profile** and displays all the basic details, the uploaded filename, and its word count.
4. Click **Download file**, open the downloaded file, and verify its contents match your upload. The server sanitizes filenames (for example, `Limerick (1).txt` becomes `Limerick_1.txt`), but preserves the bytes.
5. Click **Sign out**, then **Sign in** using the same username and password. Confirm the saved details and file reappear.
6. Refresh the profile page to confirm direct page requests work.

To show database persistence after registration without exposing hashes or file contents:

```bash
sudo sqlite3 -header -column /var/lib/aws-authenticator/users.db \
  'SELECT id, username, first_name, last_name, email, address FROM users;'
sudo sqlite3 -header -column /var/lib/aws-authenticator/users.db \
  'SELECT user_id, filename, word_count, length(content) AS bytes FROM uploads;'
```

**Screenshots:** completed registration form (password masked), profile with personal details and word count, downloaded file, sign-in page, profile after re-login, and SQLite rows. Use sample details in screenshots.

## 6. Submit the code, URL, and screenshots

The repository remote is `https://github.com/Ashanth-Ganesh/AWS-Authenticator`. To publish these changes yourself, review `git status`, add the implementation files and lockfile, commit, and push. The `.gitignore` excludes database files, environment files, SSH keys, builds, and dependencies.

If you submit an attachment instead, include the source folders, `package.json`, `package-lock.json`, `requirements.txt`, `wsgi.py`, and deployment docs. The deployment ZIP includes built UI assets; it is intended for the server, so also attach the React source when submitting source code.

Submit the **public HTTP URL** you successfully tested, for example:

```text
http://ec2-YOUR-ACTUAL-ADDRESS.us-east-2.compute.amazonaws.com
```

Keep the instance running and HTTP accessible until grading is complete. A normal public IP/DNS can change if you stop and start the instance; [AWS documents this address behavior](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-instance-addressing.html). Verify the submitted URL again after any restart.

| Assignment requirement | Implementation | Evidence to capture |
| --- | --- | --- |
| Internet-accessible EC2 | Ubuntu instance, public address, HTTP inbound rule | Running instance, AMI, key pair, network |
| Web server and SQLite | Apache/mod_wsgi, Flask, users/uploads tables | Installation, modules, schema |
| Shared source | GitHub repository or source attachment | Repository link or attachment |
| 4a: registration | `/register`, username and password | Registration form, saved username |
| 4b: basic details | First name, last name, email, address | Form, database rows |
| 4c: display after submission | Automatic navigation to `/profile` | Profile with all saved details |
| 4d: re-login | `/login`, verified username/password | Sign-in page and retrieved profile |
| 4e: file upload and storage | Registration upload, SQLite BLOB | Form upload and uploads row |
| 4e: word count and download | Profile word count and download button | Profile and downloaded text |

## Troubleshooting and updates

**Browser times out:** check the public IP, subnet route to an internet gateway, inbound TCP 80 rule, and instance status. If you enabled UFW separately, allow `Apache` and `OpenSSH` before enabling its firewall. Do not use Vite or Flask’s development server as the public web server.

**Apache welcome page appears:** run `sudo a2dissite 000-default`, `sudo a2ensite aws-authenticator`, and `sudo systemctl restart apache2`.

**HTTP 500:** inspect the app’s log:

```bash
sudo tail -n 80 /var/log/apache2/aws-authenticator-error.log
sudo tail -n 80 /var/log/apache2/error.log
```

Check that `/etc/aws-authenticator.env` exists, is `root:www-data` with mode `640`, and that `/var/lib/aws-authenticator` belongs to `www-data`. Do not paste your secret key into issue reports.

**Login never stays signed in:** `COOKIE_SECURE` must be `false` for this HTTP setup. When you add a domain and HTTPS certificate, set it to `true` and restart Apache; do not enable it before HTTPS works.

**Update the code:** rebuild and repackage locally, upload the new ZIP, extract it again with `unzip -o`, then rerun `sudo bash deploy/install.sh`. The installer preserves the session secret and existing user/file data.

**After grading:** terminate the instance and remove unneeded retained volumes or snapshots to end their ongoing charges. Export data first if you want to keep it. Check your Billing dashboard; stopping an instance alone can leave storage charges. See [AWS’s termination guide](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/terminating-instances.html).
