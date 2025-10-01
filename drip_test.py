
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pytz
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.append(str(Path(__file__).parent))

from tables import Contact, ContentInfo, get_db_session
from drip_logic import DripCampaignManager
from mail_service import send_drip_email, mail_service
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DripTester:
    def __init__(self):
        self.drip_manager = DripCampaignManager()
        self.timezone = pytz.timezone('Asia/Kolkata')
    
    def list_contacts_with_initial_email(self):
        """List all contacts who have received initial email"""
        with get_db_session() as db:
            contacts = db.query(Contact).filter(
                Contact.first_mail_date.isnot(None),
                Contact.mail_sent_status.in_([1, 2, 3])
            ).order_by(Contact.first_mail_date.desc()).all()
            
            if not contacts:
                print("\nNo contacts found with initial emails sent.")
                return []
            
            print(f"\n{'='*80}")
            print(f"Contacts with Initial Emails Sent ({len(contacts)} total)")
            print(f"{'='*80}")
            print(f"{'ID':<5} {'Email':<30} {'Status':<8} {'First Mail':<20} {'Days Ago':<10}")
            print("-" * 80)
            
            now = datetime.now(self.timezone).date()
            for contact in contacts:
                days_ago = (now - contact.first_mail_date).days if contact.first_mail_date else 0
                status_map = {1: "Stage 1", 2: "Stage 2", 3: "Stage 3", 4: "Complete"}
                status = status_map.get(contact.mail_sent_status, "Unknown")
                
                print(f"{contact.id:<5} {contact.email:<30} {status:<8} {contact.first_mail_date.strftime('%Y-%m-%d %H:%M'):<20} {days_ago:<10}")
            
            print("="*80 + "\n")
            return contacts
    
    def list_drip_eligible_contacts(self):
        """List contacts eligible for drip emails"""
        with get_db_session() as db:
            now = datetime.now(self.timezone)
            
            # Stage 1: Ready for Drip 1 (7+ days after initial)
            stage1 = db.query(Contact).filter(
                Contact.mail_sent_status == 1,
                Contact.first_mail_date.isnot(None)
            ).all()
            stage1_eligible = [c for c in stage1 if (now - c.first_mail_date).days >= 7]
            
            # Stage 2: Ready for Drip 2 (14+ days after drip 1)
            stage2 = db.query(Contact).filter(
                Contact.mail_sent_status == 2,
                Contact.drip1_date.isnot(None)
            ).all()
            stage2_eligible = [c for c in stage2 if (now - c.drip1_date).days >= 14]
            
            # Stage 3: Ready for Drip 3 (30+ days after drip 2)
            stage3 = db.query(Contact).filter(
                Contact.mail_sent_status == 3,
                Contact.drip2_date.isnot(None)
            ).all()
            stage3_eligible = [c for c in stage3 if (now - c.drip2_date).days >= 30]
            
            print(f"\n{'='*80}")
            print("Contacts Eligible for Drip Emails")
            print(f"{'='*80}")
            
            if stage1_eligible:
                print(f"\nReady for Drip 1 ({len(stage1_eligible)} contacts):")
                print(f"{'ID':<5} {'Email':<30} {'Days Since Initial':<20}")
                print("-" * 80)
                for c in stage1_eligible:
                    days = (now - c.first_mail_date).days
                    print(f"{c.id:<5} {c.email:<30} {days} days")
            
            if stage2_eligible:
                print(f"\nReady for Drip 2 ({len(stage2_eligible)} contacts):")
                print(f"{'ID':<5} {'Email':<30} {'Days Since Drip 1':<20}")
                print("-" * 80)
                for c in stage2_eligible:
                    days = (now - c.drip1_date).days
                    print(f"{c.id:<5} {c.email:<30} {days} days")
            
            if stage3_eligible:
                print(f"\nReady for Drip 3 ({len(stage3_eligible)} contacts):")
                print(f"{'ID':<5} {'Email':<30} {'Days Since Drip 2':<20}")
                print("-" * 80)
                for c in stage3_eligible:
                    days = (now - c.drip2_date).days
                    print(f"{c.id:<5} {c.email:<30} {days} days")
            
            if not any([stage1_eligible, stage2_eligible, stage3_eligible]):
                print("\nNo contacts currently eligible for drip emails.")
            
            print("="*80 + "\n")
            
            return stage1_eligible, stage2_eligible, stage3_eligible
    
    def set_contact_drip_stage(self, email: str, stage: int):
        """
        Set a contact to a specific drip stage for testing
        Stages: 1=ready for drip1, 2=ready for drip2, 3=ready for drip3, 4=completed
        """
        with get_db_session() as db:
            contact = db.query(Contact).filter(Contact.email == email).first()
            if not contact:
                logger.error(f"Contact {email} not found")
                return None
            
            if contact.first_mail_date is None:
                logger.error(f"Contact {email} has no initial email sent (first_mail_date is None)")
                return None
            
            now = datetime.now(self.timezone)
            
            if stage == 1:
                # Ready for drip 1
                contact.mail_sent_status = 1
                contact.first_mail_date = now - timedelta(days=8)  # 8 days ago
                contact.drip1_date = None
                contact.drip2_date = None
                contact.drip3_date = None
                logger.info(f"Set {email} to stage 1 (ready for drip 1)")
                
            elif stage == 2:
                # Ready for drip 2
                contact.mail_sent_status = 2
                contact.first_mail_date = now - timedelta(days=22)
                contact.drip1_date = now - timedelta(days=15)  # 15 days ago
                contact.drip2_date = None
                contact.drip3_date = None
                logger.info(f"Set {email} to stage 2 (ready for drip 2)")
                
            elif stage == 3:
                # Ready for drip 3
                contact.mail_sent_status = 3
                contact.first_mail_date = now - timedelta(days=53)
                contact.drip1_date = now - timedelta(days=46)
                contact.drip2_date = now - timedelta(days=31)  # 31 days ago
                contact.drip3_date = None
                logger.info(f"Set {email} to stage 3 (ready for drip 3)")
                
            elif stage == 4:
                # All drips completed
                contact.mail_sent_status = 4
                contact.first_mail_date = now - timedelta(days=84)
                contact.drip1_date = now - timedelta(days=77)
                contact.drip2_date = now - timedelta(days=62)
                contact.drip3_date = now - timedelta(days=32)
                logger.info(f"Set {email} to stage 4 (all drips completed)")
            
            db.commit()
            db.refresh(contact)
            return contact
    
    def test_single_drip(self, email: str, drip_number: int):
        """Test sending a specific drip email to a contact"""
        with get_db_session() as db:
            contact = db.query(Contact).filter(Contact.email == email).first()
            if not contact:
                logger.error(f"Contact {email} not found")
                return False
            
            if contact.first_mail_date is None:
                logger.error(f"Contact {email} has no initial email sent. Cannot test drips.")
                return False
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing Drip {drip_number} for {email}")
            logger.info(f"Contact: {contact.name} - {contact.company_name}")
            logger.info(f"{'='*60}")
            
            # Generate and display the content
            subject, body = mail_service.generate_drip_content(contact, drip_number)
            
            print(f"\nSubject: {subject}")
            print(f"\nBody:\n{body}")
            print("\n" + "="*60 + "\n")
            
            # Ask for confirmation
            response = input(f"Send this drip email to {email}? (y/n): ")
            if response.lower() == 'y':
                success = send_drip_email(contact, drip_number, db)
                if success:
                    logger.info(f"✓ Successfully sent Drip {drip_number}")
                    return True
                else:
                    logger.error(f"✗ Failed to send Drip {drip_number}")
                    return False
            else:
                logger.info("Send cancelled by user")
                return False
    
    def test_drip_sequence(self, email: str, start_stage: int = 1, send_emails: bool = False):
        """
        Test the entire drip sequence for a contact
        start_stage: Which drip to start from (1, 2, or 3)
        send_emails: If True, actually send emails. If False, just generate content
        """
        with get_db_session() as db:
            contact = db.query(Contact).filter(Contact.email == email).first()
            if not contact:
                logger.error(f"Contact {email} not found")
                return
            
            if contact.first_mail_date is None:
                logger.error(f"Contact {email} has no initial email sent.")
                return
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing Drip Sequence for {email}")
            logger.info(f"Contact: {contact.name} - {contact.company_name}")
            logger.info(f"Starting from Drip {start_stage}")
            logger.info(f"{'='*60}\n")
            
            for drip_num in range(start_stage, 4):
                logger.info(f"\n--- Drip {drip_num} ---")
                
                subject, body = mail_service.generate_drip_content(contact, drip_num)
                
                print(f"\nSubject: {subject}")
                print(f"\nBody:\n{body}\n")
                print("-" * 60)
                
                if send_emails:
                    response = input(f"Send Drip {drip_num}? (y/n/q to quit): ")
                    if response.lower() == 'q':
                        break
                    elif response.lower() == 'y':
                        success = send_drip_email(contact, drip_num, db)
                        if success:
                            logger.info(f"✓ Sent Drip {drip_num}")
                        else:
                            logger.error(f"✗ Failed to send Drip {drip_num}")
                            break
                    else:
                        logger.info("Skipped Drip {drip_num}")
    
    def view_contact_status(self, email: str):
        """View the current status of a contact"""
        with get_db_session() as db:
            contact = db.query(Contact).filter(Contact.email == email).first()
            if not contact:
                logger.error(f"Contact {email} not found")
                return
            
            print(f"\n{'='*60}")
            print(f"Contact Status: {email}")
            print(f"{'='*60}")
            print(f"Name: {contact.name}")
            print(f"Company: {contact.company_name}")
            print(f"Industry: {contact.industry}")
            print(f"Status: {contact.status}")
            print(f"Mail Sent Status: {contact.mail_sent_status}")
            print(f"\nDates:")
            print(f"  First Mail: {contact.first_mail_date}")
            print(f"  Drip 1: {contact.drip1_date}")
            print(f"  Drip 2: {contact.drip2_date}")
            print(f"  Drip 3: {contact.drip3_date}")
            
            # Get email history
            emails = db.query(ContentInfo).filter(
                ContentInfo.contact_id == contact.id
            ).order_by(ContentInfo.created_at).all()
            
            print(f"\nEmail History ({len(emails)} emails):")
            for email_rec in emails:
                print(f"  - {email_rec.email_type}: {email_rec.subject[:50]} ({email_rec.created_at})")
            print(f"{'='*60}\n")


def main():
    """Interactive test menu"""
    tester = DripTester()
    
    while True:
        print("\n" + "="*60)
        print("DRIP CAMPAIGN TESTER (Existing Contacts)")
        print("="*60)
        print("1. List all contacts with initial emails sent")
        print("2. List contacts eligible for drip emails")
        print("3. Set contact drip stage (for testing)")
        print("4. Test single drip email")
        print("5. Test complete drip sequence")
        print("6. View contact status")
        print("7. Run drip processor (process all eligible)")
        print("8. Exit")
        print("="*60)
        
        choice = input("\nSelect option (1-8): ")
        
        try:
            if choice == '1':
                tester.list_contacts_with_initial_email()
                
            elif choice == '2':
                tester.list_drip_eligible_contacts()
                
            elif choice == '3':
                email = input("Enter email: ")
                stage = int(input("Enter stage (1=ready for drip1, 2=ready for drip2, 3=ready for drip3, 4=completed): "))
                tester.set_contact_drip_stage(email, stage)
                
            elif choice == '4':
                email = input("Enter email: ")
                drip_num = int(input("Enter drip number (1, 2, or 3): "))
                tester.test_single_drip(email, drip_num)
                
            elif choice == '5':
                email = input("Enter email: ")
                start = int(input("Start from drip (1, 2, or 3): "))
                send = input("Actually send emails? (y/n): ").lower() == 'y'
                tester.test_drip_sequence(email, start, send)
                
            elif choice == '6':
                email = input("Enter email: ")
                tester.view_contact_status(email)
                
            elif choice == '7':
                print("\nRunning drip processor...")
                confirm = input("This will process ALL eligible contacts. Continue? (yes/no): ")
                if confirm.lower() == 'yes':
                    tester.drip_manager.process_drips()
                    print("Drip processing complete")
                else:
                    print("Cancelled")
                
            elif choice == '8':
                print("Exiting...")
                break
                
            else:
                print("Invalid option")
                
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()