    except Exception as error:
        st.error("Could not generate recommendations.")
        st.code(str(error))

    st.divider()
    st.subheader("Recommended NGOs for a Donation")

    available = get_available_donations()

    if available:
        selected_donation_id = st.selectbox(
            "Choose a donation",
            [d["donation_id"] for d in available],
            key="ngo_donation_select"
        )

        selected_donation = next(
            d for d in available
            if d["donation_id"] == selected_donation_id
        )

        # Sample NGO directory for demonstration.
        # Replace these sample entries with verified NGO records.
        ngos = [
            {
                "ngo_id": "NGO-01",
                "name": "Chennai Community Kitchen",
                "location": "Adyar",
                "daily_need": 100
            },
            {
                "ngo_id": "NGO-02",
                "name": "Helping Hands",
                "location": "Anna Nagar",
                "daily_need": 60
            },
            {
                "ngo_id": "NGO-03",
                "name": "Hope Foundation",
                "location": "Tambaram",
                "daily_need": 40
            },
            {
                "ngo_id": "NGO-04",
                "name": "Care Network",
                "location": "Velachery",
                "daily_need": 75
            }
        ]

        ngo_results = rec.recommend_ngos(
            selected_donation,
            ngos
        )

        if ngo_results:
            st.dataframe(
                pd.DataFrame(ngo_results),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No eligible NGO recommendations found.")
    else:
        st.info("Add a donation first to see NGO recommendations.")


# ====================================================
# 5. DONATION RECORDS
# ====================================================
elif page == "Donation Records":

    st.header("📋 All Donation Records")

    donations = get_all_donations()

    if donations:
        df = pd.DataFrame(donations)

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        csv_data = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download Records as CSV",
            data=csv_data,
            file_name="foodbridge_donations.csv",
            mime="text/csv"
        )

        st.subheader("Mark Donation as Completed")

        claimed_donations = [
            d for d in donations
            if d.get("status") == "Claimed"
        ]

        if claimed_donations:
            selected_completed_id = st.selectbox(
                "Select claimed donation",
                [d["donation_id"] for d in claimed_donations],
                key="completed_donation"
            )

            if st.button("Mark as Completed"):
                try:
                    success = store.update_status(
                        selected_completed_id,
                        "Completed",
                        "Pickup completed"
                    )

                    if success:
                        st.success("Donation marked as completed.")
                        st.rerun()
                    else:
                        st.warning("Could not update this donation.")

                except Exception as error:
                    st.error("Status update failed.")
                    st.code(str(error))
        else:
            st.info("There are no claimed donations waiting for completion.")





