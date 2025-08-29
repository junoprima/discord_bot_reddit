#!/usr/bin/env python3
"""
Quick check of your current Firestore structure
"""

import os
from firebase_admin import credentials, firestore, initialize_app
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_firestore():
    """Check current Firestore data structure"""
    try:
        # Your Firebase credentials path
        firebase_creds = r"D:\Working\Coding\redditbot\firebase_key.json"
        
        print(f"🔍 Checking Firebase credentials at: {firebase_creds}")
        
        if not os.path.exists(firebase_creds):
            print(f"❌ Firebase credentials file not found at: {firebase_creds}")
            return
        
        print("✅ Firebase credentials file found")
        
        # Initialize Firebase
        cred = credentials.Certificate(firebase_creds)
        initialize_app(cred)
        firestore_client = firestore.client()
        
        print("✅ Firebase initialized successfully")
        print("\n" + "="*60)
        print("📊 CURRENT FIRESTORE DATA")
        print("="*60)
        
        # Check channel_configs collection
        print("\n🔥 CHANNEL CONFIGS:")
        configs = firestore_client.collection("channel_configs").stream()
        channel_count = 0
        
        for config in configs:
            data = config.to_dict()
            channel_id = data.get("channel_id", config.id)
            subreddit = data.get("subreddit", "N/A")
            webhook_url = data.get("webhook_url", "N/A")
            bot_name = data.get("bot_name", "N/A")
            last_post_id = data.get("last_post_id", "N/A")
            
            print(f"\n📺 Channel ID: {channel_id}")
            print(f"   Subreddit: r/{subreddit}")
            print(f"   Bot Name: {bot_name}")
            print(f"   Last Post ID: {last_post_id}")
            print(f"   Webhook: {'✅ Set' if webhook_url != 'N/A' else '❌ Missing'}")
            
            channel_count += 1
        
        print(f"\n📈 Total Channels: {channel_count}")
        
        # Check sent_post_ids collection
        print("\n🆔 SENT POST IDS:")
        sent_posts = firestore_client.collection("sent_post_ids").stream()
        total_posts = 0
        post_channels = 0
        
        for sent_post in sent_posts:
            channel_id = sent_post.id
            data = sent_post.to_dict()
            post_ids = data.get("post_ids", [])
            
            print(f"📝 Channel {channel_id}: {len(post_ids)} post IDs")
            total_posts += len(post_ids)
            post_channels += 1
        
        print(f"\n📈 Total Post IDs: {total_posts} across {post_channels} channels")
        
        print("\n" + "="*60)
        print("✅ FIRESTORE CHECK COMPLETE")
        print(f"📊 Summary: {channel_count} channels, {total_posts} post IDs")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = check_firestore()
    if success:
        print("\n💡 Next steps:")
        print("1. Copy this data structure to your .env file")
        print("2. Run the migration script")
        print("3. Verify the migration worked")
    else:
        print("\n❌ Fix the Firebase connection first")